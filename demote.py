"""
Demote all TL1 users to TL0. They will no longer be able to post until they
take the quiz. Send them a notification of explanation.

Can't run this until pydiscourse is fixed (although this is hanging in the
request rather than returning Payload Too Big, but it must be the same issue.)

v1.1.1 has delete_group_member and add_group_member. How is this related to
trust levels?

Never finished this as we decided not to demote users, but I found the way to
do it, by reverse-engineering and pushing the button to do it manually. In
Chrome, at least, be sure to check the box *not to clear the network traffic
on reload.
"""

from time import time, sleep
from client506 import MyDiscourseClient, create_client
from log import logger


def demote():
    client = create_client()
    tl1_users = client.members_of_group('trust_level_1')

    for user in tl1_users:
        try:
            print 'adding user details for ', user['username']
            client.add_user_details(user)

            print user




            sleep(5)
        except Exception, exc:
            print 'failed to get details or update user: ', exc
            logger.exception('Users failed')

    sleep(3600)


if __name__ == '__main__':
    demote()
