#!/usr/bin/env bash

source /usr/local/bin/virtualenvwrapper.sh
cd `dirname $0`
workon py3
echo `date "+%Y年%m月%d日 %H:%M:%S"` >> /var/log/django_cron.err.log
python3 manage.py runcrons 2>&1 >>/var/log/django_cron.log


