from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from src.services.telegram_service import TelegramService
from src.services.supabase_service import SupabaseService
from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AutoMessageScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.supabase = SupabaseService()
        self.jobs: Dict[str, dict] = {}
        self.telegram_services: Dict[str, TelegramService] = {}

    def start(self):
        self.scheduler.start()

    def stop(self):
        self.scheduler.shutdown()

    def register_service(self, gateway_number: str, service: TelegramService):
        self.telegram_services[gateway_number] = service

    async def send_scheduled_message(self, gateway_number: str, client_real_id: str, message_template: str):
        service = self.telegram_services.get(gateway_number)
        if not service or not service.is_connected:
            logger.warning(f"Service not connected for gateway {gateway_number}")
            return

        client = self.supabase.get_client_by_real_id(client_real_id, gateway_number)
        if not client:
            logger.warning(f"Client not found: {client_real_id}")
            return

        platform_ids = client.platform_identifiers
        telegram_id = platform_ids.get("telegram")
        if not telegram_id:
            logger.warning(f"No Telegram ID for client {client.id}")
            return

        try:
            message = message_template.replace("{{name}}", client.masked_identity)
            await service.send_message(int(telegram_id), message)
            logger.info(f"Auto message sent to {client.masked_identity}")
        except Exception as e:
            logger.error(f"Failed to send auto message: {e}")

    def schedule_message(self, job_id: str, gateway_number: str, client_real_id: str,
                         message: str, cron_expression: str = None,
                         run_once: bool = False, run_date: datetime = None):
        if cron_expression:
            parts = cron_expression.split()
            trigger = CronTrigger(
                minute=parts[0] if len(parts) > 0 else "*",
                hour=parts[1] if len(parts) > 1 else "*",
                day=parts[2] if len(parts) > 2 else "*",
                month=parts[3] if len(parts) > 3 else "*",
                day_of_week=parts[4] if len(parts) > 4 else "*",
            )
            job = self.scheduler.add_job(
                self.send_scheduled_message,
                trigger=trigger,
                args=[gateway_number, client_real_id, message],
                id=job_id,
                replace_existing=True
            )
        elif run_once and run_date:
            job = self.scheduler.add_job(
                self.send_scheduled_message,
                trigger='date',
                run_date=run_date,
                args=[gateway_number, client_real_id, message],
                id=job_id,
                replace_existing=True
            )
        else:
            return False

        self.jobs[job_id] = {
            "gateway_number": gateway_number,
            "client_real_id": client_real_id,
            "message": message,
            "next_run": str(job.next_run_time) if job else None,
        }
        return True

    def cancel_job(self, job_id: str):
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            self.jobs.pop(job_id, None)

    def cleanup_completed_jobs(self):
        stale = []
        for job_id, job_info in self.jobs.items():
            job = self.scheduler.get_job(job_id)
            if job is None:
                stale.append(job_id)
        for jid in stale:
            self.jobs.pop(jid, None)

    def get_pending_jobs(self) -> List[dict]:
        self.cleanup_completed_jobs()
        result = []
        for job_id, job_info in self.jobs.items():
            job = self.scheduler.get_job(job_id)
            result.append({
                "id": job_id,
                **job_info,
                "next_run": str(job.next_run_time) if job else None,
            })
        return result
