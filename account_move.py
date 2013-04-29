import time
import datetime
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
import tools
import wizard
from tools.translate import _
import os


class account_move(osv.osv):
    _inherit = 'account.move'
    _columns = {
        'currency_id':fields.many2one('res.currency','Currency')
        }
account_move()