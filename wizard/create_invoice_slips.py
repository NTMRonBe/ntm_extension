import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _

class create_invoice_slips():
    _name='create.invoice.slips'
    
    def create_slips(self, cr, uid, ids, context=None):
        slip_pool = self.pool.get('invoice.slip')
        slip_line_pool = self.pool.get('invoice.slip.line')
        query = "select * from invoice_slip_upload where imported=False"
        cr.execute(query)
        for t in cr.dictfetchall():
            trans_name = t['transaction_id']
            type=t['transaction_type']
            debit_account = t['debit_account']
            date = t['invoice_date']
            user = t['user_id']
            credit_account = t['credit_account']
            currency=t['currency']
            query2 = ("""select * from account_analytic_account where code_short="""%(debit_account))
            cr.execute(query2)
            for da in cr.dictfetchall():
                debit_account = da['id']
            query3=("""select * from account_account where code="""%(credit_account))
            cr.execute(query3)
            for ca in cr.dictfetchall():
                credit_account = ca['id']
            query4 = ("""select * from invoice_slip where transaction_id="""%(trans_name))
            cr.execute(query4)
            new_line = {}
            for u in cr.dictfetchall():
                if not u:
                    new_line = {
                        'transaction_id':trans_name,
                        'transaction_type':type,
                        'debit_account':debit_account,
                        'invoice_date':date,
                        'user_id':user,
                        'credit_account':credit_account,
                        'currency':currency,
                        }
                    slip_pool.create(cr, uid, new_line)
        return {'type': 'ir.actions.act_window_close'}
create_invoice_slips()