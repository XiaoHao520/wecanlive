from django_cron import CronJobBase, Schedule
from datetime import datetime, timedelta

from . import models as m


class AutomaticShelvesCronJob(CronJobBase):
    # > crontab -e  */5 * * * *
    # RUN_EVERY_MINS = 1
    RUN_EVERY_MINS = 0.1
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'core.AutomaticShelvesCronJob'  # a unique code

    # TODO: 服务器定时执行命令

    def do(self):

        # 执行所有延时命令
        m.PlannedTask.trigger_all()

        now = datetime.now()

        # 每一个小时更新一次全部排行榜
        rank_record_target_plan = m.PlannedTask.objects.filter(
            method='update_rank_record',
            date_planned__gt=now,
        ).first()
        if not rank_record_target_plan:
            date_planned = now + timedelta(minutes=15)
            m.PlannedTask.make('update_rank_record', date_planned)

        update_member_check_history_plan = m.PlannedTask.objects.filter(
            method='update_member_check_history',
            date_planned__gt=now,
        ).first()
        if not update_member_check_history_plan:
            date_planned = datetime(now.year, now.month, now.day) + timedelta(days=1)
            m.PlannedTask.make('update_member_check_history', date_planned)

        update_activity_settle_plan = m.PlannedTask.objects.filter(
            method='settle_activity',
            date_planned__gt=now,
        ).first()
        if not update_activity_settle_plan:
            date_planned = datetime(now.year, now.month, now.day) + timedelta(days=1)
            m.PlannedTask.make('settle_activity', date_planned)