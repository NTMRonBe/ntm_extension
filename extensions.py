import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp


class ntm_res_partner_extension(osv.osv):
    _name = 'ntm.res.partner.extension'
    _description = 'Partner Extension'
    _columns = {
            'partner_id':fields.many2one('res.partner','Partner Name'),
            'code':fields.char('Dictionary',size=100),
            }
ntm_res_partner_extension()

class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'
    _description = 'Partner'
    _columns = {
        'partner_dict':fields.one2many('ntm.res.partner.extension','partner_id','Dictionary'),
        }
res_partner()

class account_analytic_account(osv.osv):
        
    _inherit = 'account.analytic.account'
    _columns = {
            'code_short':fields.char('Short Code',size=64),
            'code_accpac':fields.char('Accpac Code',size=64),
            'code':fields.char('Code',size=64),
            'second_currency':fields.many2one('res.currency','Secondary Currency'),
            'total_balance': fields.float('Total Balance'),
            'normal_account':fields.many2one('account.account','Related Normal Account'),
            }
    def compute_total_balance(self, cr, uid, ids, context=None):
        query = ("""
                select sum(amount_currency) as total, account_id from account_analytic_line group by account_id
                """)
        cr.execute(query)
        for t in cr.dictfetchall():
            account_id = t['account_id']
            total_amount = t['total']
            query1 = ("""
            update account_analytic_account set total_balance=%s where id=%s
            """%(total_amount,account_id))
            cr.execute(query1)
        return True
        
account_analytic_account()

class res_currency_rate(osv.osv):
    _inherit = 'res.currency.rate'
    _columns = {
        'weighted_rate':fields.float('Weighted Rate', readonly=True),
        'post_rate':fields.float('Post Rate'),
        'end_rate':fields.float('End Rate'),
        }
res_currency_rate()

class account_account(osv.osv):
    _inherit = 'account.account'
    _columns = {
        'pr':fields.boolean('Partially Revaluated'),
        'to_be_moved':fields.boolean('To be moved to net equity?'),
        'gain_loss':fields.many2one('account.account','Gain Loss Account'),
        'gain_loss_acc':fields.boolean('Is this a Gain/Loss Account?'),
        'gain_loss_consolidated':fields.boolean('Will this have Consolidated Entries?')
        }
account_account()


class account_move_line(osv.osv):
    _inherit = 'account.move.line'
    _columns = {
        'post_rate':fields.float('Post Rate'),
        'br_credit':fields.float('Before Revaluation Credit'),
        'br_debit':fields.float('Before Revaluation Debit'),
        'reval_post_rate':fields.float('Revaluation Post Rate'),
        }
account_move_line()