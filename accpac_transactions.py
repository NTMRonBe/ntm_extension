import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from datetime import datetime
from dateutil.relativedelta import relativedelta    
    
class accpac_entry(osv.osv):
    _name = 'accpac.entry'
    _description = 'Accpac Journal Entries'
    _columns = {
        'account_id':fields.char('Account ID',size=64),
        'src_curr':fields.many2one('res.currency','Source Currency'),
        'region':fields.char('Region',size=64),
        'posting_seq':fields.char('Posting Sequence',size=64),
        'cnt_detail':fields.char('CNT Detail',size=64),
        'entry_date':fields.date('Entry Date'),
        'batch_nbr':fields.char('Batch Number',size=64),
        'entry_nbr':fields.char('Entry Number',size=64),
        'trans_nbr':fields.char('Transaction Number',size=64),
        'name':fields.char('Description',size=100),
        'ref':fields.char('Reference',size=100),
        'transamt':fields.float('Transaction Amount'),
        'src_amount':fields.float('Source Amount'),
        'rate_date':fields.date('Rate Date'),
        'conv_rate':fields.float('Conversion Rate'),
        }
accpac_entry()
