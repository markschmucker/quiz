"""
A flask server to handle webhooks from Typeform. This is similar to the general
forms webhook which adds users to a group if they self-certify. I've made a copy
for this application because it's a little different- for example it might be
different to determine whether they've passed the test, and it will take a
different action- unlock their trust level and add them to the passed_quiz group.
"""

from flask import Flask, render_template, flash, request
import logging
import json
from pprint import pprint, pformat
from client506 import create_client
from ses import send_simple_email
from pydiscourse.exceptions import (
    DiscourseClientError
)

recipients = ['markschmucker@yahoo.com',]

logger = logging.getLogger('quiz_webhook')
file_handler = logging.FileHandler('quiz_webhook.log')
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)

logger.info('running quiz web hook server.py')

app = Flask(__name__)
app.config.from_object(__name__)
app.config['SECRET_KEY'] = '7d441f27d441f27567d4jjf2b6176a'


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class RequestHandler:
    def __init__(self, data):
        self.client = create_client(1)
        self.data = data
        self.answers = self.data['form_response']['answers']
        self.score = self.data['form_response']['calculated']['score']
        self.username = self.data['form_response']['hidden']['username']
        self.user = self.client.user(self.username)
        pprint(self.data)

    def user_is_in_group(self, group_name, username):
        members = self.client.members_of_group(group_name)
        membernames = [x['username'] for x in members]
        return username in membernames

    def add_to_group(self, group_name, username):
        group = self.client.my_group(group_name)
        self.client.add_group_members(group['id'], [username, ])

    def process(self):
        # just the fact that we're here is enough if we keep circle-back logic
        passed = True
        if passed:
            # Unlock them from TL0. Discourse will recognize this soon and will promote them to TL1.
            # See https://meta.discourse.org/t/understanding-discourse-trust-levels/90752/61
            # Actually it seems to recognize immediately?
            self.client.trust_level_lock(self.user['id'], False)

            group_name = 'passed_quiz'
            try:
                self.add_to_group(group_name, self.username)
                subject = 'User was added to %s' % group_name
                s = '%s was added to the group %s because they passed the quiz.' % (self.username, group_name)
            except DiscourseClientError, exc:
                subject = 'User could not be added to %s' % group_name
                s = '%s could not be added to the group %s. Maybe they are already a member?' % (self.username, group_name)

            s += '<br>'
            url = 'https://forum.506investorgroup.com/g/%s' % group_name
            s += 'To change this, visit the %s group settings at ' % group_name
            s += url
            s += '.'
            for recipient in recipients:
                send_simple_email(recipient, subject, s)
                print 'sent email'
"""
Thurs pm this almost worked. Unlocked JohnDoe and it seemed to immediately promote him
to TL1, so that's a bonus if they don't have to wait a day. However it couldn't add him
to eh paassed_quiz group. I did get an email. ok the group name was wrong. fixed.
need to fix the quiz (dunderhead pic is wrong). And send a
notification from here? No- there's not a way in client and not worth it.
So the dunderhead pic is the only thing.
"""


@app.route('/quiz_complete', methods=['POST'])
def quiz_complete_handler():
    if request.method == 'POST':
        print 'quiz is complete: '
        data = request.json
        q = RequestHandler(data)
        q.process()
        return '', 200
    else:
        return '', 400

@app.route('/user_event', methods=['POST'])
def user_event_handler():

    # Currently we're only interested in user_created. Other webhooks are available,
    # for users, topics, and posts. (However not for user_added_to_group). See
    # https://meta.discourse.org/t/setting-up-webhooks/49045.

    headers = request.headers
    pprint(headers)

    event = request.headers['X-Discourse-Event']
    print 'event: ', event

    if event == 'user_created':
        print 'user was created'
        data = request.json
        pprint(data)
        # need to convert to html, not this
        # report_str = pformat(data)

        send_simple_email('markschmucker@yahoo.com', 'User Created', 'no text yet...')

        d = json.loads(request.json)
        user_id = d['id']
        email = d['email']
        username = d['username']
        msg = '%d %s %s' % (user_id, username, email)

        send_simple_email('markschmucker@yahoo.com', 'User Created, interpreted', msg)

        client = create_client(1)
        client.trust_level_lock(user_id, True)
        send_simple_email('markschmucker@yahoo.com', 'User Locked', msg)

        return '', 200
    else:
        return '', 400


if __name__ == "__main__":
    # Digests use 8081, forms use 8082, tracking_pixel and resourse server use 8083,
    # not sure if either of those two on 8083 are running; run this on 8084 (it's open).
    app.run(host="0.0.0.0", port=8084, debug=True, threaded=True)
