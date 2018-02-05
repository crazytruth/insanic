import requests
import ujson as json

slack_gen = None

def _slack_developers(new_version, changelog):
    params = {}
    # params['channel'] = '#dev-project-msa'
    params['channel'] = '#dev-black-hole'
    params['username'] = "Insanic"
    params[
        'text'] = f'Gotta go insanely fast! New version [{new_version}] has been released. `pip install -U insanic` to update.'
    params['icon_emoji'] = ":sanic:"
    params['attachments'] = {}
    params['attachments']['text'] = changelog


    slack_webhook_url = 'https://hooks.slack.com/services/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'

    yield

    # f = urllib.urlopen(slack_webhook_url, params)
    r = requests.post(slack_webhook_url, data=json.dumps(params))


def release_after(data):
    global slack_gen

    slack_gen.next()

def prerelease_middle(data):
    global slack_gen
    slack_gen = _slack_developers(data['new_version'], data['history_last_release'])
    slack_gen.next()
