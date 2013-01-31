import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class account_period_close_ntm(osv.osv):
    """
        close period
    """
    _name = "account.period.close.ntm"
    _description = "NTM Period Close"
    _columns = {
        'currency_ids':fields.one2many('account.period.close.ntm.currencies','period_close_id','Currencies', ondelete="cascade"),
        'state':fields.selection([
                                  ('draft','Draft'),
                                  ('compute','Compute'),
                                  ('verify','Verify'),
                                  ])
    }
    _defaults = {
            'state':'draft',
            }
    
    def create(self, cr, uid, ids, context=None):
        apcn_pool = self.pool.get('account.period.close.ntm')
        for form in self.read(cr, uid, ids, context=context):           
            values = {
                'id':form['id'],
                'state':form['state']
                }
            apcn_pool.create(cr, uid, values)
        return True
    
    def data_save(self, cr, uid, ids, context=None):
        period_pool = self.pool.get('account.period')

        mode = 'done'
        for form in self.read(cr, uid, ids, context=context):
            if form['sure']:
                for id in context['active_ids']:
                    cr.execute('update account_journal_period set state=%s where period_id=%s', (mode, id))
                    cr.execute('update account_period set state=%s where id=%s', (mode, id))

                    # Log message for Period
                    for period_id, name in period_pool.name_get(cr, uid, [id]):
                        period_pool.log(cr, uid, period_id, "Period '%s' is closed, no more modification allowed for this period." % (name))
        return {'type': 'ir.actions.act_window_close'}
        
    def compute_wr_per_line(self, cr, uid, ids, context=None):
        apcnc_pool = self.pool.get('account.period.close.ntm.currencies')
        period_pool = self.pool.get('account.period')
        period_id1 = 0.00
        comp_id = 0
        company_curr = 0
        for form in self.read(cr, uid, ids, context=context):
            form_id = form['id']
            for id in context['active_ids']:
                for period_id in period_pool.browse(cr, uid, [id]):
                    period_id1 = period_id.id         
                    comp_id = period_id.company_id.id   
        for close_period in self.browse(cr, uid, ids, context=None):
            for currency_line in close_period.currency_ids:
                currency_line_id = currency_line.id
                currency_id = currency_line.currency_id.id
                company_get = self.pool.get('res.company').browse(cr, uid, comp_id)
                wr = 0
                if company_get.currency_id:
                    company_curr = company_get.currency_id.id
                    query = ("""select * from forex_transaction where period_id = %s and currency_one=%s and currency_two=%s"""%(period_id1,company_curr,currency_id))
                    cr.execute(query)
                    amount_1 = 0.00
                    amount_2 = 0.00
                    for t in cr.dictfetchall():
                        transaction_id = t['id']
                        amount_one = t['amount_currency1']
                        amount_two = t['amount_currency2']
                        amount_1 += amount_one
                        amount_2 += amount_two
                    amount_3 = 0.00
                    amount_4 = 0.00
                    query = ("""select * from forex_transaction where period_id = %s and currency_one=%s and currency_two=%s"""%(period_id1,currency_id,company_curr))
                    cr.execute(query)
                    for t in cr.dictfetchall():
                        transaction_id = t['id']
                        amount_one = t['amount_currency1']
                        amount_two = t['amount_currency2']
                        amount_3 += amount_one
                        amount_4 += amount_two
                    c1_amount = amount_1 - amount_4
                    c2_amount = amount_2 - amount_3
                    if c1_amount < 0.00:
                        c1_amount = -1.00 * c1_amount
                    if c2_amount < 0.00:
                        c2_amount = -1.00 * c2_amount
                    if c2_amount > 0.00 and c1_amount > 0.00:
                        wr = c2_amount / c1_amount
                        netsvc.Logger().notifyChannel("query", netsvc.LOG_INFO, ' '+str(period_id1))
                        netsvc.Logger().notifyChannel("query", netsvc.LOG_INFO, ' '+str(currency_line_id))
                        netsvc.Logger().notifyChannel("query", netsvc.LOG_INFO, ' '+str(currency_id))
                        netsvc.Logger().notifyChannel("query", netsvc.LOG_INFO, ' '+str(wr))
                query = ("""update account_period_close_ntm_currencies set weighted_rate=%s, post_rate=%s where id=%s"""%(wr, wr, currency_line_id))
                cr.execute(query)
        return True
            
    def fetch_currencies(self, cr, uid, ids, context=None):
        apcnc_pool = self.pool.get('account.period.close.ntm.currencies')
        period_pool = self.pool.get('account.period')
        for form in self.read(cr, uid, ids, context=context):
            form_id = form['id']
            for id in context['active_ids']:
                for period_id in period_pool.browse(cr, uid, [id]):
                    period_id1 = period_id.id
                    comp_curr = period_id.company_id.currency_id.id
                    netsvc.Logger().notifyChannel("period_id", netsvc.LOG_INFO, ' '+str(period_id1))
                    date_start = period_id.date_start
                    netsvc.Logger().notifyChannel("period_id", netsvc.LOG_INFO, ' '+str(date_start))
                    date_start = "'"+date_start+"'"
                    date_stop = period_id.date_stop
                    netsvc.Logger().notifyChannel("period_id", netsvc.LOG_INFO, ' '+str(date_stop))
                    date_stop = "'"+date_stop+"'"
                    query = ("""select distinct(currency_id) from account_move_line where currency_id!=(select currency_id from res_company where id=(select company_id from res_users where id=%s)) and period_id=%s"""%(uid,period_id1))
                    netsvc.Logger().notifyChannel("query", netsvc.LOG_INFO, ' '+str(query))
                    cr.execute(query)
                    for t in cr.dictfetchall():
                        wr=0.00
                        currency_id = t['currency_id']
                        query = ("""select * from forex_transaction where period_id = %s and currency_one=%s and currency_two=%s"""%(period_id1,comp_curr,currency_id))
                        cr.execute(query)
                        amount_1 = 0.00
                        amount_2 = 0.00
                        for t in cr.dictfetchall():
                            amount_one = t['amount_currency1']
                            amount_two = t['amount_currency2']
                            amount_1 += amount_one
                            amount_2 += amount_two
                        amount_3 = 0.00
                        amount_4 = 0.00
                        query = ("""select * from forex_transaction where period_id = %s and currency_one=%s and currency_two=%s"""%(period_id1,currency_id,comp_curr))
                        cr.execute(query)
                        for t in cr.dictfetchall():
                            amount_one = t['amount_currency1']
                            amount_two = t['amount_currency2']
                            amount_3 += amount_one
                            amount_4 += amount_two
                        c1_amount = amount_1 - amount_4
                        c2_amount = amount_2 - amount_3
                        if c1_amount < 0.00:
                            c1_amount = -1.00 * c1_amount
                        if c2_amount < 0.00:
                            c2_amount = -1.00 * c2_amount
                        if c2_amount > 0.00 and c1_amount > 0.00:
                            wr = c2_amount / c1_amount
                        query = ("""select rate from res_currency_rate where currency_id=%s and name>=%s and name<=%s"""%(currency_id,date_start,date_stop))
                        cr.execute(query)
                        for t in cr.dictfetchall():
                            rate = t['rate']
                            currencies_list = {
                                'currency_id':currency_id,
                                'start_rate':rate,
                                'weighted_rate':wr,
                                'post_rate':wr,
                                'period_close_id':form_id,
                                }
                            apcnc_pool.create(cr, uid, currencies_list)
        return self.write(cr, uid, ids, {'state':'compute'})

account_period_close_ntm()

class account_period_close_ntm_currencies(osv.osv):
	_name = 'account.period.close.ntm.currencies'
	_columns = {
		'currency_id':fields.many2one('res.currency', "Currency"),
		'weighted_rate':fields.float("Weighted Rate"),
		'start_rate':fields.float("Start Rate"),
		'post_rate':fields.float("Post Rate"),
		'end_rate':fields.float("End Rate"),
		'period_close_id':fields.many2one('account.period.close.ntm'),
	}
account_period_close_ntm_currencies()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: