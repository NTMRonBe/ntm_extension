import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from datetime import datetime


class ntm_help(osv.osv):
    _name = 'ntm.error'
    _description = "Help - Defined Errors"
    _columns = {
        'name':fields.char('Error Code', size=32, readonly=True),
        'description':fields.char('Description', size=100, readonly=True),
        'model_id':fields.many2one('ir.model','Model ID'),
        'sequence':fields.integer('Sequence', readonly=True),
        'fix':fields.text('Fix Procedure', readonly=True),
        }
ntm_help()
