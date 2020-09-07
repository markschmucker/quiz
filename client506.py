from pydiscourse111.client import DiscourseClient
from pydiscourse111.exceptions import (
    DiscourseError, DiscourseServerError, DiscourseClientError
)

import datetime, pytz
import dateutil.parser
from sets import Set
import requests
from log import logger
from time import sleep
from time import time


class MyDiscourseClient(DiscourseClient):
    def get_post(self, post_id, **kwargs):
        return self._get('/posts/{0}.json'.format(post_id), **kwargs)

    # copied from the client code, changed category -> c
    def category(self, name, parent=None, **kwargs):
        return self._get(u"/c/{0}.json".format(name), **kwargs)

    def my_categories(self):
        # categories is /categories.json, this is a superset of that, and
        # includes subcategories.
        val = self._get(u"/site.json")
        return val['categories']

    def my_groups(self, **kwargs):
        # base class groups doesn't work
        return self._get("/groups.json", **kwargs)

    def my_group(self, group_name):
        # base class group doesn't work
        return self._get("/groups/{0}.json".format(group_name))['group']

    def category_details(self, category_id):
        val = self._get(u"/c/%d/show.json" % category_id)
        cat = val['category']

        # create a comma-separated string of groups allowed to see this category
        groups = cat['group_permissions']
        groups_str = ','.join([g['group_name'] for g in groups])
        cat.update({'group_permissions': groups_str})

        # Add a parent_id field to this cat, and log that to the db
        # The API has it the opposite way- subcategories for each category-
        # so look and see if any parent lists us as a child.
        cat['parent_id'] = None
        parents = self._get(u"/categories.json")['category_list']['categories']
        for parent in parents:
            for sub in parent.get('subcategory_ids', []):
                if category_id == sub:
                    cat['parent_id'] = parent['id']
                    break

        return cat

    def recent_posts(self):
        return self._get(u"/posts.json")

    def topic_from_id(self, id):
        return self._get(u"/t/{0}".format(id))

    # def my_members_of_group(self, group_name):
    #     # base class group doesn't work
    #     # Note my other members_of_group() below- that one works
    #     return self._get("/groups/{0}/members.json".format(group_name))['members']


    def members_of_group(self, groupname):
        # This worked until 18 June 2019; now seems to require pagination.
        # 1000 seems to be the max allowed. See my post at:
        # https://meta.discourse.org/t/groups-api-now-requires-pagination-in-latest-release/120982
        #data = self._get(u"/groups/{0}/members.json".format(groupname), limit=10000, offset=0)

        members = []
        pagesize = 1000
        for page in range(100):
            data = self._get(u"/groups/{0}/members.json".format(groupname), limit=pagesize, offset=page*pagesize)
            if data:
                m = data['members']
                if not m:
                    break
                members.extend(m)
                sleep(10)
            else:
                break
        #print 'members_of_group got %d members' % len(members)
        #for m in members:
        #    print 'got: ', m
        return members

    def user_details(self, username):
        # not sure need ussername exactly
        # / users / Adam_Weissman.json
        for attempt in range(10):
            try:
                return self._get(u"/users/{0}.json".format(username))
            except DiscourseClientError, requests.ConnectionError:
                print 'user details failed; trying again'
                sleep(1)

    def user_admin_details(self, user_id):
        # adding August 2020
        for attempt in range(10):
            try:
                return self._get(u"/admin/users/{0}.json".format(user_id))
            except DiscourseClientError, requests.ConnectionError:
                print 'user details failed; trying again'
                sleep(1)

    def user_email(self, username):
        for attempt in range(10):
            try:
                email_list = self._get(u"/u/{0}/emails.json".format(username))
                return email_list.get('email')
            except DiscourseClientError:
                print 'user email failed; trying again'

    # August 2020 this is not the way that gets the most details- need /admin and id.
    # Completely different endpoint.


    def add_user_details(self, user):
        details = self.user_details(user['username'])

        email = self.user_email(user['username'])
        groups = details['user']['groups']
        groups_str = ','.join([g['name'] for g in groups])
        user.update(details['user'])

        #this seems close, but it has me in the moderator group, which isn't right.
        user.update({'groups': groups_str})
        user.update({'email':email})

        # Not sure what that was all about. August 2020 adding admin user details
        admin_details = self.user_admin_details(user['id'])
        user.update(admin_details)


    def get_latest_post_id(self):
        """" Get the latest post id; we will work backwards from this id until
        posts are older than desired. This is a weird workflow but there's not a
        better way: https://meta.discourse.org/t/latest-posts-api-pagination/88589.
        """
        posts = self.recent_posts()
        ids = [post['id'] for post in posts['latest_posts']]
        return max(ids)

    def get_recent_posts(self, minutes):
        post_id = self.get_latest_post_id()
        min_desired_date = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=minutes)
        posts = []

        # The bastards put rate limits that are not editable.
        # https://meta.discourse.org/t/global-rate-limits-and-throttling-in-discourse/78612/8
        # So there is little point in using threads.
        if True:
            # created_at ends with Z, so compare to now utc time
            while 1:
                post = self.get_post(post_id)
                created_at = dateutil.parser.parse(post['created_at'])
                if created_at < min_desired_date:
                    break
                posts.append(post)
                print(len(posts))
                post_id -= 1
            return posts
        else:
            queue = Queue()
            # Create 8 worker threads
            for x in range(2):
                worker = DownloadPostWorker(self, queue, min_desired_date)
                # Setting daemon to True will let the main thread exit even though the workers are blocking
                worker.daemon = True
                worker.start()
            for _id in range(post_id, post_id-100, -1): # not enough for weekly?
                queue.put(_id)
            queue.join()
            print self.posts
            return self.posts


    def get_unique_topics(self, posts):
        topics = [post['topic_id'] for post in posts]
        return list(Set(topics))

    def add_top_level_category_to_topic(self, topic):
        # this is probably not needed now
        top_level_categories = self.my_categories()

        tlc = None
        categories = [cat for cat in self.categories() if cat['id'] == topic['category_id']]
        if categories:
            # This topic is in a top-level category
            tlc = categories[0]
        else:
            # First get the sub-category title, just to include the string
            # in the email. For example, subtopic category is 18. What is
            # the title?


            # This topic is in a sub-category, but we need the top-level
            # category to check permissions. Must iterate for it.
            for top_level_category in top_level_categories:
                print "looking for ", topic['category_id'], "in", top_level_category.get('subcategory_ids', [])
                if topic['category_id'] in top_level_category.get('subcategory_ids', []):
                    tlc = top_level_category
                    break

        topic['top_level_category'] = tlc


    def get_topics_for_posts(self, posts):

        topic_ids = self.get_unique_topics(posts)

        #At this point topics are just topic ids. Need to get the topics to see if they're visible etc.'
        topics = [self.topic_from_id(t) for t in topic_ids]

        # not sure if this does anything
        topics = [t for t in topics if t['visible']]

        # eliminate greetings from the bot etc, and maybe private messages
        topics = [t for t in topics if t['category_id']]

        for t in topics:
            self.add_top_level_category_to_topic(t)

        # Assemble posts by topic
        for topic in topics:
            topic_posts = [p for p in posts if p['topic_id'] == topic['id']]
            topic_posts.reverse()
            topic.update({'topic_posts': topic_posts})

        return topics

    def bump_topic(self, topic_id, delta_seconds=0):
        url = "t/%d/change-timestamp" % topic_id
        return self._put(url, timestamp=int(time()+delta_seconds))

    # new, not tested
    # http://forum.506investorgroup.com/t/14003/invite?username=admin
    # maybe can't test from browser because post? Should be able to compare to change-timestamp
    # above- there is something slightly different in the API docs between the two.

    # complains about no email field, even though the API docs don't require it
    def send_invite(self, topic_id, username, email):
        url = "t/%d/invite" % topic_id
        # doesn't work if PM?
        # why am I passing an id here?
        # return self._post(url, id=14003, username=username, email=email)
        # anyway the new client has an invite method which takes a custom message- use that.


    """ Overriding _request to try 10 times """
    # The base client seems to do this now so I'm removing mine


def get_api_key():
    # store the api key in a file not in the public git repo
    f = file('api_key', 'rt')
    s = f.read()
    f.close()
    return s.strip()

# Helper for threads
def create_client(max_attempts=10):
    client = MyDiscourseClient(
        'https://forum.506investorgroup.com/',
        api_username='admin',
        api_key=get_api_key(),
        timeout=5)
    client.max_attempts = max_attempts
    return client


# v 1.1.1 is not in pypi yet, so I've monkey-patched my notebook. I do have 1.1.1 but they
# haven't updated the version number in __init__ either. They have since added retries, so
# I've remove my retry stuff (two methods in client506).

# The fix does fix members_of_group, but breaks bump_topic, don't care for now.


if __name__ == "__main__":
    client = create_client()
    # members = client.members_of_group('trust_level_0')
    # for member in members:
    #    print member

    # This works, if the topic is public. Not for a PM? Not sure the criteria.
    # wait my method was ignoring the id. So don't know what the critical thing is.
    # I've seen it work though.
    # But I can't get it to work from a browser, i.e. with the following or similar,
    # perhaps because it's a post and the browser sends a get.
    # https://forum.506investorgroup.com/t/6484/invite?username=admin&email=markschmucker@yahoo.com
    resp = client.send_invite(6484, "admin", "markschmucker@yahoo.com")

    # Now I'm getting bad csrf even for things that used to work. The new API is not in
    # pypi yet, but I'll pull it manually on my notebook.
    # resp = client.bump_topic(4031, 3600*24)
    print resp
