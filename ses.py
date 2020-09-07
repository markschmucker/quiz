""""
Send emails using SES. SES Credentials must be stored in ~/.aws/credentials.
"""

import boto3
from botocore.exceptions import ClientError


def send_simple_email(recipient, subject, contents, sender="506 Investor Group <noreply@506investorgroup.com>"):
    """ Send a very simple email. Not currently used. """
    SENDER = sender
    RECIPIENT = recipient
    AWS_REGION = "us-west-2"
    SUBJECT = subject
    BODY_TEXT = ("")
    BODY_HTML = contents
    CHARSET = "UTF-8"
    client = boto3.client('ses', region_name=AWS_REGION)
    try:
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': BODY_HTML,
                    },
                    'Text': {
                        'Charset': CHARSET,
                        'Data': BODY_TEXT,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
        )
    # Display an error if something goes wrong.
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])

if __name__ == '__main__':
    send_simple_email('markschmucker@yahoo.com', 'test from ses.py', 'this is a test')
