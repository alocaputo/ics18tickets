import os
import logging
from flask import Flask, send_file, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ics18tickets import generate_ics


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICS_PATH = os.path.join(BASE_DIR, 'ics18tickets.ics')

app = Flask(__name__)


def scheduled_update():
    try:
        logger.info('Running scheduled update...')
        changed = generate_ics(output_path=ICS_PATH)
        logger.info('Scheduled update finished. changed=%s', changed)
    except Exception as e:
        logger.exception('Scheduled update failed: %s', e)


@app.route('/ics18tickets.ics')
def serve_ics():
    # Ensure file exists; generate if missing
    if not os.path.exists(ICS_PATH):
        logger.info('ICS not found on request, generating now...')
        try:
            generate_ics(output_path=ICS_PATH)
        except Exception:
            logger.exception('Failed to generate ICS on demand')
    # Send file as text/calendar so clients can subscribe
    return send_file(ICS_PATH, mimetype='text/calendar')


@app.route('/update', methods=['POST', 'GET'])
def manual_update():
    try:
        changed = generate_ics(output_path=ICS_PATH)
        return jsonify({'ok': True, 'changed': changed})
    except Exception as e:
        logger.exception('Manual update failed')
        return jsonify({'ok': False, 'error': str(e)}), 500


def main():
    # run once at startup to ensure ICS exists
    try:
        generate_ics(output_path=ICS_PATH)
    except Exception:
        logger.exception('Initial generation failed')

    # Scheduler: every Monday at 23:59 local system time
    scheduler = BackgroundScheduler()
    cron = CronTrigger(day_of_week='mon', hour=23, minute=59)
    scheduler.add_job(scheduled_update, cron, id='weekly_update')
    scheduler.start()

    # run the web server
    app.run(host='0.0.0.0', port=8067)


if __name__ == '__main__':
    main()
