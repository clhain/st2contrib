"""This module is used to send multipart MIME email messages from stackstorm.

This module handles sending emails based on account configs in config.yaml, and
arguments passed to it from stackstorm workflow execution. Optional html / text
and image portions are attached to the message and sent.
"""
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from smtplib import SMTP

from st2actions.runners.pythonrunner import Action


class SendEmail(Action):
  """Handles the sending of multipart MIME email messages from stackstorm.

    This action definition is used to send email messages containing HTML / text
    and images from stackstorm.
  """

  def run(self, email_from, email_to, email_cc, email_references,
          email_in_reply_to, subject, account, message_text, message_html,
          message_images):
    """Send a multipart html / text email with images from stackstorm.

    Args:
      email_from: From address of sender
      email_to: To address of recipient
      email_cc: Cc list of addresses to copy
      email_references: String containing message reference ids
      email_in_reply_to: String containing message id of reply email
      subject: Subject of email message
      account: name of account to use (as specified in config.yaml under project
      message_text: plain text message to send
      message_html: html containing message to send
      message_images: list of images to attach to message
    Raises:
      ValueError: if missing accounts or no imap mailboxes found
      KeyError: if the specified account is not in the configuration.
    """
    accounts = self.config.get('imap_mailboxes', None)
    if accounts is None:
      raise ValueError('"imap_mailboxes" config value is required to send '
                       'email.')
    if not accounts:
      raise ValueError('at least one account is required to send email.')

    try:
      account_data = accounts[account]
    except KeyError:
      raise KeyError('The account "{}" does not seem to appear in the '
                     'configuration. Available accounts are: {}'.format(
                         account, ','.join(accounts.keys())))

    msg_root = MIMEMultipart('related')
    msg_root['Subject'] = subject
    msg_root['From'] = email_from
    msg_root['To'] = email_to
    msg_root['Cc'] = email_cc
    msg_root['References'] = email_references
    msg_root['In-Reply-To'] = email_in_reply_to
    if email_cc:
      toaddrs = email_to.split(', ') + email_cc.split(', ')
    else:
      toaddrs = email_to.split(', ')
    msg_root.preamble = 'This is a multi-part message in MIME format.'
    msg_alt = MIMEMultipart('alternative')
    msg_root.attach(msg_alt)
    if message_text:
      msg_alt.attach(MIMEText(message_text, 'plain'))
    if message_html:
      msg_alt.attach(MIMEText(message_html, 'html'))
    if message_images:
      for image in message_images:
        name = os.path.basename(image)
        fp = open(image, 'rb')
        imgdata = fp.read()
        try:
          img = MIMEImage(imgdata)
        except TypeError:
          imgtype = name.split('.')[-1]
          img = MIMEImage(imgdata, _subtype=imgtype)
        fp.close()
        img.add_header('Content-ID', '<%s>' % name)
        msg_root.attach(img)

    s = SMTP(account_data['server'], int(account_data['port']), timeout=20)
    s.ehlo()
    s.starttls()
    s.login(account_data['username'], account_data['password'])
    s.sendmail(email_from, toaddrs, msg_root.as_string())
    s.quit()
    return
