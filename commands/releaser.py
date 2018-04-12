import os
import requests
import json

slack_parameters = None

SLACK_CHANNEL = os.environ['INSANIC_SLACK_CHANNEL']
SLACK_USERNAME = os.environ.get('SLACK_USERNAME', 'Insanic')
SLACK_WEBHOOK = os.environ['INSANIC_SLACK_WEBHOOK']

def _beautify_changelog_for_slack(changelog):
    lines = changelog.split('\n')[3:-4]
    return "*CHANGES*\n```" + "\n".join(lines) + "```"


def _prepare_slack(new_version, changelog):
    params = {}
    params['channel'] = SLACK_CHANNEL
    params['username'] = SLACK_USERNAME
    params['text'] = f'Gotta go insanely fast! New version [{new_version}] has been released. ' \
                     f'`pip install -U insanic` to update.'
    params['icon_emoji'] = ":sanic:"
    params['attachments'] = []
    params['attachments'].append({'text': _beautify_changelog_for_slack(changelog), "mrkdwn": True})

    global slack_parameters
    slack_parameters = params


def _send_slack():
    global slack_parameters
    slack_webhook_url = SLACK_WEBHOOK

    requests.post(slack_webhook_url, data=json.dumps(slack_parameters))


def release_after(data):
    _send_slack()


def prerelease_middle(data):
    _prepare_slack(data['new_version'], data['history_last_release'])
