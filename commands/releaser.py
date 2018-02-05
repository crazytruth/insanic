import requests
import json

slack_parameters = None


def _beautify_changelog_for_slack(changelog):
    lines = changelog.split('\n')[3:-4]

    beautified = ["**CHANGES:**"]
    for l in lines:
        l[0] = "*"
        beautified.append(l)

    return "\n".join(beautified)


def _prepare_slack(new_version, changelog):
    params = {}
    # params['channel'] = '#dev-project-msa'
    params['channel'] = '#dev-black-hole'
    params['username'] = "Insanic"
    params[
        'text'] = f'Gotta go insanely fast! New version [{new_version}] has been released. `pip install -U insanic` to update.'
    params['icon_emoji'] = ":sanic:"
    params['attachments'] = []
    params['attachments'].append({'text': _beautify_changelog_for_slack(changelog), "mrkdwn": True})

    global slack_parameters
    slack_parameters = params


def _send_slack():
    global slack_parameters
    slack_webhook_url = 'https://hooks.slack.com/services/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'

    r = requests.post(slack_webhook_url, data=json.dumps(slack_parameters))


def release_after(data):
    _send_slack()

def prerelease_middle(data):
    _prepare_slack(data['new_version'], data['history_last_release'])
