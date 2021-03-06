# Copyright (c) 2018, Matias Fontanini
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.

from terminaltables import AsciiTable
from terminaltables.width_and_alignment import max_dimensions
import datetime
import dateparser
import sys
import hashlib
import base64
import getpass
import re
import math
try:
    import readline
except ImportError: #Window systems don't have GNU readline
    import pyreadline.windows_readline as readline
    readline.rl.mode.show_all_if_ambiguous = "on"
from Crypto.Cipher import AES
from Crypto import Random
from dateutil.tz import tzutc, tzlocal
from models import CandleTicks

class ParameterOptionVisitor:
    def __init__(self):
        self.tokens = []
        self.parameters = []

    def visit_const_option(self, option):
        self.tokens.append(option)

    def visit_parameter_option(self, option):
        self.parameters.append(option)

def format_float(number, number_format = '{0:.8f}'):
    # Format it, then remove right zeroes and remove dot if all decimals are gone
    return number_format.format(number).rstrip('0').rstrip('.')

def format_fiat_currency(value, fiat_currency):
    fiat_currency_symbols = {
        'aud' : 'AU$ {0}',
        'brl' : 'R$ {0}',
        'cad' : 'C$ {0}',
        'chf' : '{0} CHF',
        'clp' : 'CLP$ {0}',
        'cny' : u'\u00a5{0}',
        'czk' : u'K\u010d{0}',
        'dkk' : '{0} kr',
        'eur' : u'\u20AC{0}',
        'gbp' : u'\u00a3{0}',
        'hkd' : 'HK$ {0}',
        'huf' : '{0} Ft',
        'idr' : '{0} Rp',
        'ils' : u'\u20aa{0}',
        'inr' : u'\u20b9{0}',
        'jpy' : u'\u00a5{0}',
        'krw' : u'\u20a9{0}',
        'mxn' : 'Mex$ {0}',
        'myr' : '{0} MYR',
        'nok' : '{0} kr',
        'nzd' : 'NZ$ {0}',
        'php' : u'\u20b1{0}',
        'pkr' : u'\u20a8{0}',
        'pln' : u'z\u0142{0}',
        'rub' : u'\u20bd{0}',
        'sek' : '{0} kr',
        'sgd' : 'S${0}',
        'thb' : u'\u0e3f{0}',
        'try' : u'\u20ba{0}',
        'twd' : 'NT${0}',
        'zar' : '{0} R',
        'usd' : '${0}',
    }
    if fiat_currency in fiat_currency_symbols:
        return fiat_currency_symbols[fiat_currency].format(value)
    return '{0} {1}'.format(value, fiat_currency)

def make_price_string(base_currency_price, base_currency_code, currency_price, fiat_currency):
    fiat_value = format_float(currency_price * base_currency_price, '{0:.4f}')
    return u'{0} {1} ({2})'.format(
        format_float(base_currency_price, '{0:.8f}'),
        base_currency_code,
        format_fiat_currency(fiat_value, fiat_currency),
    )

def make_table_rows(title, table_data):
    table = AsciiTable(table_data, title)
    dimensions = max_dimensions(table.table_data, table.padding_left, table.padding_right)[:3]
    output = table.gen_table(*dimensions)
    return map(lambda i: ''.join(i), list(output))

def datetime_from_utc_time(str_time):
    return dateparser.parse(str_time).replace(tzinfo=tzutc()).astimezone(tz=tzlocal())

def show_operation_dialog():
    running = True
    output = None
    all_history = [
        readline.get_history_item(i) for i in range(1, readline.get_current_history_length() + 1)
    ]
    readline.clear_history()
    while running:
        try:
            line = raw_input('Type "yes" or "no" to confirm or decline the operation: ')
        except (KeyboardInterrupt, EOFError):
            break
        if line == 'yes':
            output = True
        elif line == 'no':
            output = False
        else:
            print 'Invalid response'
        # Remove whatever the user typed so we don't see "yes" or "no" in the history
        readline.remove_history_item(readline.get_current_history_length() - 1)
        if output is not None:
            break
    for item in all_history:
        readline.add_history(item)
    return output or False

def encrypt(data, passphrase):
    key = hashlib.sha256(passphrase).digest()
    iv = Random.new().read(AES.block_size)
    encrypted = AES.new(key, AES.MODE_CFB, iv).encrypt(data)
    return base64.b64encode(iv + encrypted)

def decrypt(data, passphrase):
    key = hashlib.sha256(passphrase).digest()
    data = base64.b64decode(data)
    iv = data[:AES.block_size]
    data = data[AES.block_size:]
    return AES.new(key, AES.MODE_CFB, iv).decrypt(data)

def decrypt_file(path, passphrase):
    data = open(path).read()
    return decrypt(data, passphrase)

def ask_for_passphrase(text):
    try:
        return getpass.getpass(text)
    except (KeyboardInterrupt, EOFError):
        return None

def make_candle_label(date, interval):
    formats = {
        CandleTicks.one_minute : "%H:%M",
        CandleTicks.five_minutes : "%H:%M",
        CandleTicks.thirty_minutes : "%H:%M",
        CandleTicks.one_hour : "%H:%M",
        CandleTicks.one_day : "%d/%m"
    }
    return date.strftime(formats[interval])

def round_order_value(step, value):
    if step >= 1:
        return int(value / step) * int(step)
    else:
        decimals = format_float(step).find('1') - 1
        meta_format = "{{0:0.{0}f}}".format(decimals)
        output = float(meta_format.format(value))
        # There's still a possibility that the rounding moved the value up. If that's
        # the case, lower it by "step" and reformat it
        if output > value:
            output = float(meta_format.format(output - step))
        return output

# Finds an appropriate float format string so that it has at least 5 decimals and
# there's at least 3 non zero digits in it
def make_appropriate_float_format_string(value):
    power = int(round(math.log10(value)))
    formatted_value = format_float(value)
    match = re.search(r'[^0\.]', formatted_value)
    if match:
        decimals = match.start() - 1
    else:
        raise Exception('Non float found')
    decimals = max(decimals + 2, 5)
    if power > 0:
        decimals -= power
    return '{{0:0.{0}f}}'.format(decimals)
