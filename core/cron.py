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
        print('update_rank_record Finish')

        # 每天更新一次成员信息
        update_member_check_history_plan = m.PlannedTask.objects.filter(
            method='update_member_check_history',
            date_planned__gt=now,
        ).first()
        if not update_member_check_history_plan:
            date_planned = datetime(now.year, now.month, now.day) + timedelta(days=1)
            m.PlannedTask.make('update_member_check_history', date_planned)
        print('update_member_check_history Finish')

        # 每天更新一次
        update_activity_settle_plan = m.PlannedTask.objects.filter(
            method='settle_activity',
            date_planned__gt=now,
        ).first()
        if not update_activity_settle_plan:
            date_planned = datetime(now.year, now.month, now.day) + timedelta(days=1)
            m.PlannedTask.make('settle_activity', date_planned)
        print('settle_activity Finish')

        # 每分钟更新一次热门直播
        update_live_hot_ranking = m.PlannedTask.objects.filter(
            method='update_live_hot_ranking',
            date_planned__gt=now,
        ).first()
        if not update_live_hot_ranking:
            date_planned = now + timedelta(minutes=1)
            m.PlannedTask.make('update_live_hot_ranking', date_planned)
        print('update_live_hot_ranking Finish')

        # 每分钟更新一次直播结束
        update_live_end = m.PlannedTask.objects.filter(
            method='update_live_end',
            date_planned__gt=now,
        ).first()
        if not update_live_end:
            date_planned = now + timedelta(minutes=1)
            m.PlannedTask.make('update_live_end', date_planned)
        print('update_live_end Finish')

        # 每分钟更新一次直播日志
        update_log_leave = m.PlannedTask.objects.filter(
            method='update_live_log_leave',
            date_planned__gt=now,
        ).first()
        if not update_log_leave:
            date_planned = now + timedelta(minutes=1)
            m.PlannedTask.make('update_live_log_leave', date_planned)
        print('update_live_log_leave Finish')