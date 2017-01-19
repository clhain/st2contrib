"""Parse email headers for list of recipients, and enforce user/domain ACLs.

This module returns the list of "To", "From", and "CC" recipients based on
incoming message headers and configuration files. Also enforces user and domain
whitelisting.
"""
import email.utils
import re
import sys

from st2actions.runners.pythonrunner import Action

TO_HEADER_STRING = 'To'
FROM_HEADER_STRING = 'From'
CC_HEADER_STRING = 'Cc'
DELIVERED_TO_HEADER_STRING = 'Delivered-To'
REFERENCES_STRING = 'References'
MESSAGE_ID_STRING = 'Message-Id'


class ProcessEmailHeaders(Action):
  """Handles enhanced processing of email headers for stackstorm action flows.

     This module returns the list of "To", "From", and "CC" recipients based on
     incoming message headers and configuration files. Also enforces user and
     domain whitelisting. The class is called from stackstorm action runners.
  """

  def parse_headers(self, headers):
    """Parse To, From, and Cc fields from a list of email headers.

    Args:
      headers: List of email header arrays

    Returns:
      header_to: set of tuples containing to addresses
      header_from: set of tuples containing from addresses
      header_cc: set of tuples containing cc addresses
      header_self: set of tuples containing delivered-to address
      header_references: string containing reference message ids
      header_reply_to: string containing original reference message id
    """
    header_to = set()
    header_from = set()
    header_cc = set()
    header_self = set()
    header_reply_to = ''
    header_references = ''
    for header in headers:
      if header[0] in [TO_HEADER_STRING, FROM_HEADER_STRING, CC_HEADER_STRING,
                       DELIVERED_TO_HEADER_STRING]:
        addr_array = header[1].split(',')
        for addr in addr_array:
          addr_tuple = email.utils.parseaddr(addr)
          if header[0] == FROM_HEADER_STRING:
            header_from.add(addr_tuple)
          elif header[0] == TO_HEADER_STRING:
            header_to.add(addr_tuple)
          elif header[0] == CC_HEADER_STRING:
            header_cc.add(addr_tuple)
          elif header[0] == DELIVERED_TO_HEADER_STRING:
            header_self.add(addr_tuple)
      if header[0] == REFERENCES_STRING:
        header_references += header[1]
      if header[0] == MESSAGE_ID_STRING:
        header_reply_to = header[1]
    if header_reply_to:
      header_references = '%s %s' % (header_references, header_reply_to)
    return(header_to, header_from, header_cc, header_self, header_references,
           header_reply_to)

  def check_allowed(self, header_from, allowed_domains, allowed_users):
    """If a list of allowed domains or users is included, check sender against.

    Args:
      header_from: set of tuples containing from address info
      allowed_domains: array of permitted domains
      allowed_users: array of allowed users

    Returns:
      Boolean indicating if 'From' user is permitted to send this email
    """
    if allowed_domains:
      for domain in allowed_domains:
        for addr_tuple in header_from:
          if re.search('@'+domain+'$', addr_tuple[1]):
            return True
    if allowed_users:
      for user in allowed_users:
        for addr_tuple in header_from:
          if re.search('^'+user+'$', addr_tuple[1]):
            return True
    return False

  def add_enforced_cc(self, enforce_cc, header_to, header_cc, header_from):
    """If a list of enforced CC addresses is supplied, check / add if needed.

    Args:
      enforce_cc: list of addresses to CC
      header_to: set of address tuples in to field
      header_cc: set of address tuples in cc field
      header_from: set of address tuples in the from field

    Returns:
      header_cc: set of address tuples including enforced addrs if not present.
    """
    for cc_addr in enforce_cc:
      exists = False
      addr_tuple = email.utils.parseaddr(cc_addr)
      for to_tuple in header_to:
        if addr_tuple[1] == to_tuple[1]:
          exists = True
          break
      if not exists:
        for cc_tuple in header_cc:
          if addr_tuple[1] == cc_tuple[1]:
            exists = True
            break
      if not exists:
        for from_tuple in header_from:
          if addr_tuple[1] == from_tuple[1]:
            exists = True
            break
      if not exists:
        header_cc.add(addr_tuple)
    return header_cc

  def process_results(self, result, header_from, header_to, header_cc,
                      header_self, header_references, header_in_reply_to):
    """Join all address sets and create return object strings.

    Args:
      result: object to return to stackstorm
      header_from: set of address tuples in from field
      header_to: set of address tuples in to field
      header_cc: set of address tuples in cc field
      header_self: set of address tuples in the delivered-to field
      header_references: string of reference message ids
      header_in_reply_to: string containing original message id

    Returns:
      result: object to return to stackstorm
    """
    for addr_self in header_self:
      for addr_to in header_to.copy():
        if addr_self[1] == addr_to[1]:
          header_to.discard(addr_to)
        continue
    sys.stdout.flush()
    header_to = header_to.union(header_from)
    to_addrs = []
    for addr in header_to:
      to_addrs.append(email.utils.formataddr(addr))
    result['to'] = ', '.join(to_addrs)
    cc_addrs = []
    for addr in header_cc:
      cc_addrs.append(email.utils.formataddr(addr))
    result['cc'] = ', '.join(cc_addrs)
    result['from'] = email.utils.formataddr(header_self.pop())
    result['references'] = header_references
    result['in_reply_to'] = header_in_reply_to
    return result

  def run(self, headers, enforce_cc, allowed_domains, allowed_users):
    result = {'to': '', 'from': '', 'cc': ''}
    (header_to, header_from, header_cc, header_self, header_references,
     header_in_reply_to) = self.parse_headers(headers)
    if allowed_domains or allowed_users:
      if not self.check_allowed(header_from, allowed_domains, allowed_users):
        self.logger.info('User not permitted: %s',
                         email.utils.formataddr(header_from.pop()))
        sys.exit(1)
    if enforce_cc:
      header_cc = self.add_enforced_cc(enforce_cc, header_to, header_cc,
                                       header_from)
    result = self.process_results(result, header_from, header_to, header_cc,
                                  header_self, header_references,
                                  header_in_reply_to)
    return result
