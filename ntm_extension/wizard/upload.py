from osv import osv, fields, orm
import pooler

class upload_invoice_slips(osv.osv):
    _name="invoice.slip.upload.wizard"
    _description="Upload Wizard"
    
    def upload_entries(self, cr, uid, ids, context=None):
        is_pool=self.pool.get('invoice.slip')
        isl_pool=self.pool.get('invoice.slip.line')
        isu_pool = self.pool.get('invoice.slip.upload')
        debit_ac = 1
        credit_ac = 1
        query = "select * from invoice_slip_upload where imported=False"
        cr.execute(query)
        for t in cr.dictfetchall():
            inv_id=t['id']
            invoice_name=t['transaction_id']
            invoice_name = "'"+invoice_name+"'"
            transaction_type=t['transaction_type']
            debit_account = t['debit_account']
            debit_account = "'"+debit_account+"'"
            credit_account = t['credit_account']
            credit_account = "'"+credit_account+"'"
            comment = t['comment']
            user = t['user_id']
            amount = t['amount']
            date=t['invoice_date']
            currency = t['currency']
            debit_query = ("""
                select * from account_analytic_account where code_short=%s
                """%(debit_account))
            cr.execute(debit_query)
            for d in cr.dictfetchall():
                debit_ac=d['id']
                
            debit_query = ("""
                select id from account_account where code=%s
                """%(credit_account))
            cr.execute(debit_query)
            for d in cr.dictfetchall():
                credit_ac=d['id']
            invoice_slips = ("""select * from invoice_slip where transaction_id=%s"""%(invoice_name))
            cr.execute(invoice_slips)
            for d in cr.dictfetchall():
                    is_id = d['id']
                    inv = {
                           'transaction_type':transaction_type,
                           'debit_account':debit_ac,
                           'credit_account':credit_ac,
                           'user_id':user,
                           'currency':currency,
                           'invoice_date':date,
                           'state':'draft',
                        }
                    is_pool.write(cr, uid, is_id,inv)
                    inv = {
                        'name':comment,
                        'amount':amount,
                        'slip_id':is_id,
                        }
                    isl_pool.create(cr, uid, inv)
                    isu_pool.write(cr, uid, inv_id, {'imported':True})
        return {'type': 'ir.actions.act_window_close'}
upload_invoice_slips()