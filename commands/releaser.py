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


def _extract_changelog(data):
    start_line = None
    end_line = None

    for h in data['headings']:
        if h['version'] == data['new_version']:
            start_line = h['line']
        else:
            try:
                major, minor, patch = h['version'].split('.')
                year, month, day = h['date'].split('-')

                if major.isnumeric() and minor.isnumeric() and patch.isnumeric() and year.isnumeric() and month.isnumeric() and day.isnumeric():
                    end_line = h['line']
                    break
            except ValueError:
                pass

    return "\n".join(data['history_lines'][start_line + 2:end_line]).strip()


def _prepare_slack(new_version, data):
    changelog = _extract_changelog(data)

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
    _prepare_slack(data['new_version'], data)
