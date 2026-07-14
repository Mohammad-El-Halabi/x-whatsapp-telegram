#!/usr/bin/env python3
"""signal-call-tunnel: WebRTC audio tunnel for signal-cli voice calls on Windows.

Implements the stdin/stdout JSON control protocol expected by signal-cli's
CallManager, using aiortc for WebRTC negotiation and audio transport.

Protocol: https://github.com/AsamK/signal-cli/blob/master/docs/CALL_TUNNEL.md
"""

import sys
import json
import asyncio
import struct
import math
import base64
import os
import fractions
import logging

import numpy as np
from av import AudioFrame
import aiortc
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.mediastreams import AudioStreamTrack

logger = logging.getLogger("signal-call-tunnel")


class SineAudioTrack(AudioStreamTrack):
    """Generates a 440 Hz sine wave as audio source."""
    kind = "audio"

    def __init__(self):
        super().__init__()
        self._timestamp = 0
        self._sample_rate = 48000
        self._samples_per_frame = 960

    async def recv(self):
        pts = self._timestamp
        self._timestamp += self._samples_per_frame
        t_start = pts / self._sample_rate
        t_end = self._timestamp / self._sample_rate
        ts = np.linspace(t_start, t_end, self._samples_per_frame, endpoint=False)
        samples = np.sin(ts * 440.0 * 2.0 * np.pi) * 0.3
        stereo = np.column_stack([samples, samples])
        s16 = (stereo * 32767).astype(np.int16)
        frame = AudioFrame.from_ndarray(s16.T, format="s16", layout="stereo")
        frame.sample_rate = self._sample_rate
        frame.pts = pts
        frame.time_base = fractions.Fraction(1, self._sample_rate)
        return frame


def send_event(event: dict):
    line = json.dumps(event) + "\n"
    sys.stdout.write(line)
    sys.stdout.flush()


class SignalCallTunnel:
    def __init__(self):
        self.pc: RTCPeerConnection = None
        self.call_id = 0
        self.is_outgoing = False
        self._queue: asyncio.Queue = None
        self._done = asyncio.Event()
        self._audio_track = None

    async def run(self):
        # Read config from stdin (first line)
        config_line = await asyncio.to_thread(sys.stdin.readline)
        if not config_line:
            logger.error("No config received")
            return
        config = json.loads(config_line)
        self.call_id = config["call_id"]
        self.is_outgoing = config.get("is_outgoing", True)
        logger.info("Config: call_id=%s, is_outgoing=%s", self.call_id, self.is_outgoing)

        send_event({"type": "ready"})

        # Start stdin reader
        self._queue = asyncio.Queue()
        stdin_task = asyncio.create_task(self._read_stdin_loop())

        # Create RTCPeerConnection
        self.pc = RTCPeerConnection()
        self._audio_track = SineAudioTrack()
        self.pc.addTrack(self._audio_track)

        @self.pc.on("track")
        def on_track(track):
            logger.info("Remote track: %s", track.kind)

        @self.pc.on("icecandidate")
        def on_icecandidate(candidate):
            if candidate is not None:
                c = {
                    "component": candidate.component,
                    "foundation": candidate.foundation,
                    "ip": candidate.ip,
                    "port": candidate.port,
                    "priority": candidate.priority,
                    "protocol": candidate.protocol,
                    "type": candidate.type,
                }
                opaque = base64.b64encode(json.dumps(c).encode()).decode()
                send_event({
                    "type": "sendIce",
                    "callId": self.call_id,
                    "candidates": [{"opaque": opaque}],
                })

        @self.pc.on("connectionstatechange")
        def on_connectionstatechange():
            state = self.pc.connectionState
            logger.info("Connection state: %s", state)
            state_map = {
                "connecting": "Connecting",
                "connected": "Connected",
                "failed": "Ended",
                "disconnected": "Ended",
                "closed": "Ended",
            }
            mapped = state_map.get(state)
            if mapped == "Ended":
                send_event({"type": "stateChange", "state": "Ended", "reason": "connection_failed"})
                self._done.set()
            elif mapped:
                send_event({"type": "stateChange", "state": mapped})

        # Process control messages
        await self._process_loop()

        stdin_task.cancel()
        await self.pc.close()

    async def _read_stdin_loop(self):
        try:
            while True:
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    await self._queue.put(None)
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    await self._queue.put(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning("Invalid JSON: %s", e)
        except Exception as e:
            logger.error("stdin error: %s", e)
            await self._queue.put(None)

    async def _process_loop(self):
        while True:
            msg = await self._queue.get()
            if msg is None:
                break
            await self._handle_control(msg)

    async def _handle_control(self, msg: dict):
        msg_type = msg.get("type", "")
        logger.debug("Control: %s", msg_type)

        if msg_type == "createOutgoingCall":
            pass

        elif msg_type == "proceed":
            if self.is_outgoing:
                await self._create_offer()

        elif msg_type == "receivedOffer":
            opaque_b64 = msg.get("opaque", "")
            if opaque_b64:
                opaque = base64.b64decode(opaque_b64)
                sdp_data = json.loads(opaque.decode("utf-8", errors="replace"))
                desc = RTCSessionDescription(
                    type=sdp_data.get("type", "offer"),
                    sdp=sdp_data.get("sdp", ""),
                )
                await self.pc.setRemoteDescription(desc)
                answer = await self.pc.createAnswer()
                await self.pc.setLocalDescription(answer)
                import json as _json
                answer_opaque = base64.b64encode(
                    _json.dumps({
                        "sdp": answer.sdp,
                        "type": "answer",
                    }).encode()
                ).decode()
                send_event({
                    "type": "sendAnswer",
                    "callId": self.call_id,
                    "opaque": answer_opaque,
                })

        elif msg_type == "receivedAnswer":
            opaque_b64 = msg.get("opaque", "")
            if opaque_b64:
                opaque = base64.b64decode(opaque_b64)
                data = json.loads(opaque.decode("utf-8"))
                desc = RTCSessionDescription(
                    type=data.get("type", "answer"),
                    sdp=data.get("sdp", ""),
                )
                await self.pc.setRemoteDescription(desc)

        elif msg_type == "receivedIce":
            candidates = msg.get("candidates", [])
            for c in candidates:
                try:
                    raw = base64.b64decode(c) if isinstance(c, str) else base64.b64decode(c.get("opaque", ""))
                    ice_data = json.loads(raw.decode("utf-8", errors="replace"))
                    candidate = RTCIceCandidate(
                        component=ice_data.get("component", 1),
                        foundation=ice_data.get("foundation", "0"),
                        ip=ice_data.get("ip", "0.0.0.0"),
                        port=ice_data.get("port", 9),
                        priority=ice_data.get("priority", 0),
                        protocol=ice_data.get("protocol", "udp"),
                        type=ice_data.get("type", "host"),
                    )
                    await self.pc.addIceCandidate(candidate)
                except Exception as e:
                    logger.warning("ICE candidate error: %s", e)

        elif msg_type == "accept":
            pass

        elif msg_type == "hangup":
            logger.info("Hangup for call %s", self.call_id)
            send_event({"type": "stateChange", "state": "Ended", "reason": "local_hangup"})
            self._done.set()

    async def _create_offer(self):
        try:
            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)
            opaque = base64.b64encode(
                json.dumps({"sdp": offer.sdp, "type": "offer"}).encode()
            ).decode()
            send_event({
                "type": "sendOffer",
                "callId": self.call_id,
                "opaque": opaque,
            })
        except Exception as e:
            logger.error("Create offer error: %s", e)
            send_event({"type": "error", "message": str(e)})
            self._done.set()


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="[tunnel] %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    tunnel = SignalCallTunnel()
    try:
        asyncio.run(tunnel.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
