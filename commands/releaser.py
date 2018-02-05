import requests

def _slack_developers(new_version):
    params = {}
    params['channel'] = '#dev-project-msa'
    params['username'] = "INSANIC RELEASE!"
    params['text'] = f'New version [{new_version}] has been released. `pip install -U insanic` to update.'
    params['icon_emoji'] = ":sanic:"

    slack_webhook_url = 'https://hooks.slack.com/services/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'

    # f = urllib.urlopen(slack_webhook_url, params)
    r = requests.post(slack_webhook_url, data=json.dumps(params))

def middle(data):
    _slack_developers(data[''])
    return
