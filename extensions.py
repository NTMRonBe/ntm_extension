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
    
    def _get_bank_id(self, cr, uid, context=None):
        if context is None:
            context = {}
        type_inv = context.get('type', 'out_invoice')
        user = self.pool.get('res.partner').browse(cr, uid, uid, context=context)
        partner_id = context.get('id', user.id)
        journal_obj = self.pool.get('res.partner.bank')
        res = journal_obj.search(cr, uid, [('partner_id', '=', partner_id)],limit=1)
        return res and res[0] or False
    
    _inherit = 'res.partner'
    _description = 'Partner'
    _columns = {
        'partner_dict':fields.one2many('ntm.res.partner.extension','partner_id','Dictionary'),
        'bank_id':fields.many2one('res.partner.bank','Bank Account'),
        'property_account_payable': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Account Payable",
            method=True,
            view_load=True,
            domain="[('type', '=', 'payable')]",
            help="This account will be used instead of the default one as the payable account for the current partner"),
        'property_account_receivable': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Account Receivable",
            method=True,
            view_load=True,
            domain="[('type', '=', 'receivable')]",
            help="This account will be used instead of the default one as the receivable account for the current partner"),
        }
res_partner()

class account_analytic_account(osv.osv):
        
    _inherit = 'account.analytic.account'
    _columns = {
            'code_short':fields.char('Short Code',size=64),
            'code_accpac':fields.char('Accpac Code',size=64),
            'code':fields.char('Code',size=64),
            'normal_account':fields.many2one('account.account','Related Normal Account'),
            'report':fields.selection([
                                ('pal','Profit and Loss'),
                                ('soa','Statement of Account')
                                ], 'Report Type'),
            }
    '''
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
       ''' 
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
        'is_pr':fields.boolean('Partially Revaluated'),
        'to_be_moved':fields.boolean('To be moved at EOY'),
        'equity_account':fields.many2one('account.account','Equity Account'),
        'gain_loss':fields.many2one('account.account','Gain Loss Account',domain=[('gain_loss_acc','=',True),('type','in',['other','liquidity'])]),
        'gain_loss_acc':fields.boolean('Is this a Gain/Loss Account?'),
        'code_short':fields.char('Code Short',size=16),
        'code_accpac':fields.char('Code Accpac',size=16),
        'closing_account':fields.many2one('account.account','Closing Account'),
        }
account_account()


class account_move_line(osv.osv):
    _inherit = 'account.move.line'
    _columns = {
        'post_rate':fields.float('Post Rate',digits=(16,6)),
        'br_credit':fields.float('Before Revaluation Credit'),
        'br_debit':fields.float('Before Revaluation Debit'),
        'reval_post_rate':fields.float('Revaluation Post Rate',digits=(16,6)),
        }
account_move_line()

class account_subscription(osv.osv):
    _inherit = 'account.subscription'
    _columns = {
        'period_nbr': fields.integer('Interval', required=True),
        }
account_subscription()