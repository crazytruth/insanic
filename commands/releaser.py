import requests
import json

slack_gen = None


def _beautify_changelog_for_slack(changelog):
    lines = changelog.split('\n')[3:-3]
    lines = ["CHANGES:"] + lines
    return "\n".join(lines)


def _slack_developers(new_version, changelog):
    params = {}
    # params['channel'] = '#dev-project-msa'
    params['channel'] = '#dev-black-hole'
    params['username'] = "Insanic"
    params[
        'text'] = f'Gotta go insanely fast! New version [{new_version}] has been released. `pip install -U insanic` to update.'
    params['icon_emoji'] = ":sanic:"
    params['attachments'] = []
    params['attachments'].append({'text': _beautify_changelog_for_slack(changelog), "mrkdwn": True})


    slack_webhook_url = 'https://hooks.slack.com/services/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'

    yield

    # f = urllib.urlopen(slack_webhook_url, params)
    r = requests.post(slack_webhook_url, data=json.dumps(params))


def release_after(data):
    global slack_gen
    try:
        next(slack_gen)
    except:
        pass

def prerelease_middle(data):
    global slack_gen
    slack_gen = _slack_developers(data['new_version'], data['history_last_release'])
    next(slack_gen)
