
import logging

logger = logging.getLogger('quiz_webhook')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

file_handler = logging.FileHandler('quiz_webhook.log')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

#logger.addHandler(mail_handler)
logger.addHandler(file_handler)
logger.setLevel(logging.WARNING)
logger.info('Starting...')
