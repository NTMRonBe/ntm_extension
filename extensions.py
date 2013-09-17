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

class res_company(osv.osv):
    _inherit = 'res.company'
    _columns = {
        'transit_php':fields.many2one('account.account','PHP Transit Account', required=True),
        'transit_usd':fields.many2one('account.account','USD Transit Account', required=True),
        'phone_bill_ap':fields.many2one('account.account','Phonebill Payable Account', required=True),
        'other_ap':fields.many2one('account.account','Other Payable Accounts', required=True),
        'contribution':fields.float('Contribution Percentage'),
        'donations':fields.many2one('account.account','Donations Account', required=True),     
        'bank_charge':fields.many2one('account.account','Bank Charges Account', required=True),
        'contributions_acct':fields.many2one('account.account','Contributions Account'),
        'def_gain_loss':fields.many2one('account.account','Default Exchange Gain/Loss'),
        }
res_company()

class res_partner(osv.osv):
    
    _inherit = 'res.partner'
    _description = 'Partner'
    _columns = {
        'partner_dict':fields.one2many('ntm.res.partner.extension','partner_id','Dictionary'),
        'project':fields.boolean('Projects'),
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
        'project_id':fields.many2one('account.analytic.account','Project Account'),
        }
res_partner()

class aaa_accpac(osv.osv):
    _name = 'account.accpac'
    _description = 'Accpac Accounts Matcher'
    _columns = {
        'name':fields.char('Account Number',size=64),
        'code':fields.char('Code to Match',size=64),
        'description':fields.char('Account Description',size=64),
        'analytic_id':fields.many2one('account.analytic.account','Analytic Account'),
        'account_id':fields.many2one('account.account','Normal Account'),
        'state':fields.selection([
                        ('matched','Matched'),('nomatched','No Match'),
                        ],'Matching State', readonly=True),
        }
aaa_accpac()

class aaa_accpac_wiz(osv.osv_memory):
    _name = 'account.accpac.wiz'
    _description = "Accpac Matcher Wizard"
    
    def match_accounts(self, cr, uid, ids, context=None):
        accpac_ids = self.pool.get('account.accpac').search(cr, uid, [('state','=',False)])
        for accpac in accpac_ids:
            accpac_read = self.pool.get('account.accpac').read(cr, uid, accpac,context=None)
            normal_search = self.pool.get('account.account').search(cr, uid,[('code','=',accpac_read['code'])])
            if normal_search:
                self.pool.get('account.accpac').write(cr, uid, accpac,{'state':'matched','account_id':normal_search[0]})
            elif not normal_search:
                analytic_search = self.pool.get('account.analytic.account').search(cr, uid, [('code','=',accpac_read['code'])])
                if analytic_search:
                    self.pool.get('account.accpac').write(cr, uid, accpac,{'state':'matched','analytic_id':analytic_search[0]})
                elif not analytic_search:
                    self.pool.get('account.accpac').write(cr, uid, accpac,{'state':'nomatched'})
        return {'type': 'ir.actions.act_window_close'}
aaa_accpac_wiz()

class phone_pins(osv.osv):
    _name = 'phone.pin'
    _description = "Phone Pin Assignment"
    _columns = {
        'name':fields.char('Phone Pin',size=6),
        'account_id':fields.many2one('account.analytic.account','Account Name', ondelete='cascade'),
        'description':fields.char('Description',size=64),
        }
phone_pins()

class account_analytic_account(osv.osv):
        
    _inherit = 'account.analytic.account'
    _columns = {
            'phone_pin':fields.one2many('phone.pin','account_id','Phone Pins'),
            'code_short':fields.char('Short Code',size=64),
            'accpac_ids':fields.one2many('account.accpac','analytic_id','Accpac Codes'),
            'code':fields.char('Code',size=64),
            'ntm_type':fields.selection([('income','Income'),('expense','Expense')],'Account Type'),
            'supplier':fields.related('partner_id','supplier',type='boolean',store=True, string='People and Team',readonly=True),
            'project':fields.related('partner_id','project',type='boolean',store=True, string='Project',readonly=True),
            'normal_account':fields.many2one('account.account','Related Normal Account'),
            'voucher_expense':fields.boolean('Include on voucher expense distribution?'),
            'project_account':fields.boolean('Project Account?'),
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

class account_allocations(osv.osv):
    _name = 'account.allocations'
    _description = "Account Allocation"
    _columns = {
        'account_id':fields.many2one('account.account','Account ID', ondelete='cascade'),
        'analytic_id':fields.many2one('account.analytic.account','Analytic Account', ondelete='cascade'),
        'name':fields.char('Description',size=64),
        'percentage':fields.float('Percentage'),
        }
    
    def create(self, cr, uid, vals, context=None):
        account_id = vals['account_id']
        totalPercentage = vals['percentage']
        for allocations in self.pool.get('account.allocations').search(cr, uid, [('account_id','=',account_id)]):
            allocationRead = self.pool.get('account.allocations').read(cr, uid, allocations, ['percentage'])
            totalPercentage +=allocationRead['percentage']
            print totalPercentage
        if totalPercentage > 100.00:
            raise osv.except_osv(('Error!'),('Total percentage will be greater than 100!'))
        elif totalPercentage<=100.00:
            return super(account_allocations, self).create(cr, uid, vals, context)
account_allocations()

class account_account(osv.osv):
    
    def __compute(self, cr, uid, ids, field_names, arg=None, context=None,
                  query='', query_params=()):
        """ compute the balance, debit and/or credit for the provided
        account ids
        Arguments:
        `ids`: account ids
        `field_names`: the fields to compute (a list of any of
                       'balance', 'debit' and 'credit')
        `arg`: unused fields.function stuff
        `query`: additional query filter (as a string)
        `query_params`: parameters for the provided query string
                        (__compute will handle their escaping) as a
                        tuple
        """
        mapping = {
            'balance': "COALESCE(SUM(l.debit),0) " \
                       "- COALESCE(SUM(l.credit), 0) as balance",
            'debit': "COALESCE(SUM(l.debit), 0) as debit",
            'credit': "COALESCE(SUM(l.credit), 0) as credit",
        }
        #get all the necessary accounts
        children_and_consolidated = self._get_children_and_consol(cr, uid, ids, context=context)
        #compute for each account the balance/debit/credit from the move lines
        accounts = {}
        sums = {}
        if children_and_consolidated:
            aml_query = self.pool.get('account.move.line')._query_get(cr, uid, context=context)

            wheres = [""]
            if query.strip():
                wheres.append(query.strip())
            if aml_query.strip():
                wheres.append(aml_query.strip())
            filters = " AND ".join(wheres)
            self.logger.notifyChannel('addons.'+self._name, netsvc.LOG_DEBUG,
                                      'Filters: %s'%filters)
            # IN might not work ideally in case there are too many
            # children_and_consolidated, in that case join on a
            # values() e.g.:
            # SELECT l.account_id as id FROM account_move_line l
            # INNER JOIN (VALUES (id1), (id2), (id3), ...) AS tmp (id)
            # ON l.account_id = tmp.id
            # or make _get_children_and_consol return a query and join on that
            request = ("SELECT l.account_id as id, " +\
                       ', '.join(map(mapping.__getitem__, field_names)) +
                       " FROM account_move_line l" \
                       " WHERE l.account_id IN %s " \
                            + filters +
                       " GROUP BY l.account_id")
            params = (tuple(children_and_consolidated),) + query_params
            cr.execute(request, params)
            self.logger.notifyChannel('addons.'+self._name, netsvc.LOG_DEBUG,
                                      'Status: %s'%cr.statusmessage)

            for res in cr.dictfetchall():
                accounts[res['id']] = res

            # consolidate accounts with direct children
            children_and_consolidated.reverse()
            brs = list(self.browse(cr, uid, children_and_consolidated, context=context))
            currency_obj = self.pool.get('res.currency')
            while brs:
                current = brs[0]
#                can_compute = True
#                for child in current.child_id:
#                    if child.id not in sums:
#                        can_compute = False
#                        try:
#                            brs.insert(0, brs.pop(brs.index(child)))
#                        except ValueError:
#                            brs.insert(0, child)
#                if can_compute:
                brs.pop(0)
                for fn in field_names:
                    sums.setdefault(current.id, {})[fn] = accounts.get(current.id, {}).get(fn, 0.0)
                    for child in current.child_id:
                        if child.company_id.currency_id.id == current.company_id.currency_id.id:
                            sums[current.id][fn] += sums[child.id][fn]
                        else:
                            sums[current.id][fn] += currency_obj.compute(cr, uid, child.company_id.currency_id.id, current.company_id.currency_id.id, sums[child.id][fn], context=context)
        res = {}
        null_result = dict((fn, 0.0) for fn in field_names)
        for id in ids:
            res[id] = sums.get(id, null_result)
        return res
    
    def _compute_amount(self, cr, uid, ids, field, arg, context=None):
        rec = self.browse(cr, uid, ids, context=None)
        result = {}
        for r in rec:
            amount1 = 0.00
            amount2 = 0.00
            amount = 0.00
            for accounts in self.pool.get('account.move.line').search(cr, uid,[('account_id','=',r.id)]):
                account = self.pool.get('account.move.line').read(cr, uid, accounts,['debit','credit','amount_currency'])
                if account['debit']>0.00:
                    amount1 += account['amount_currency']
                if account['credit']>0.00:
                    amount2 += account['amount_currency']
            amount = amount1 - amount2
            result[r.id] = amount
        return result
    
    _inherit = 'account.account'
    _columns = {
        'is_pr':fields.boolean('Partially Revaluated'),
        'allocated':fields.boolean('Allocated'),
        'to_be_moved':fields.boolean('To be moved at EOY'),
        'include_pool':fields.boolean('Included in Money Pool'),
        'equity_account':fields.many2one('account.account','Equity Account'),
        'gain_loss':fields.many2one('account.account','Gain Loss Account',domain=[('gain_loss_acc','=',True),('type','in',['other','liquidity'])]),
        'gain_loss_acc':fields.boolean('Is this a Gain/Loss Account?'),
        'code_short':fields.char('Code Short',size=16),
        'accpac_ids':fields.one2many('account.accpac','account_id','Accpac Codes'),
        'closing_account':fields.many2one('account.account','Closing Account'),
        'post_amount': fields.function(_compute_amount, digits_compute=dp.get_precision('Account'), method=True, type='float', string='Total Amount', store=False),
        'equity_reval_value_acc':fields.many2one('account.analytic.account','Equity Revaluated Value'),
        'equity_gain_loss_acc':fields.many2one('account.analytic.account','Equity Gain Loss Value'),
        'equity_check':fields.boolean('Is this an Equity Account?'),
        'allocation_ids':fields.one2many('account.allocations','account_id','Account Allocations'),
        }
    
    def onchange_equity_bool(self, cr, uid, ids, include_pool):
        res={}
        if include_pool:
            res = {'value':
                   {
                    'gain_loss_acc':False,
                    'gain_loss':False,
                    'equity_check':False,
                    'equity_reval_value_acc':False,
                    'equity_gain_loss_acc':False,
                }}
        return res
account_account()


class account_move_line(osv.osv):
    _inherit = 'account.move.line'
    _columns = {
        'post_rate':fields.float('Post Rate',digits=(16,6)),
        'br_credit':fields.float('Before Revaluation Credit'),
        'br_debit':fields.float('Before Revaluation Debit'),
        'reval_post_rate':fields.float('Revaluation Post Rate',digits=(16,6)),
        'partner_id': fields.many2one('res.partner', 'Entity', select=1, ondelete='restrict'),
        'currency_id': fields.many2one('res.currency', 'Encoding Currency', help="The optional other currency if it is a multi-currency entry."),
        'amount_currency': fields.float('Encoding Amount', help="The amount expressed in an optional other currency if it is a multi-currency entry.", digits_compute=dp.get_precision('Account')),
        }
account_move_line()

class account_subscription(osv.osv):
    _inherit = 'account.subscription'
    _columns = {
        'period_nbr': fields.integer('Interval', required=True),
        }
account_subscription()

class res_request_link(osv.osv):
    _inherit = 'res.request.link'
    _columns = {
        'for_liquidation':fields.boolean('For Liquidation'),
        }
res_request_link()

class account_journal(osv.osv):
    _inherit="account.journal"
    _columns = {
        'type': fields.selection([('sale', 'Sale'),('sale_refund','Sale Refund'), 
                                ('purchase', 'Purchase'), ('purchase_refund','Purchase Refund'),
                                ('transfer','Fund Transfer'),
                                ('other_expenses','Other Expenses'), 
                                ('forex','Foreign Exchanges'),
                                ('vd','Voucher Distribution'),
                                ('pc_transfer','Petty Cash Transfers'),
                                ('pbd','Phone Bill Distribution'),
                                ('arj','Accounts Revaluation'),
                                ('ved','Vehicle Expense Distribution'),
                                ('iat','Internal Account Transfers'),
                                ('regional_report','Regional Report'),
                                ('cash', 'Cash'), ('bank', 'Bank and Cheques'), ('pettycash', 'Petty Cash'), ('disbursement', 'Petty Cash Disbursement'), 
                                ('general', 'General'), ('situation', 'Opening/Closing Situation')], 'Type', size=32, required=True,
                                 help="Select 'Sale' for Sale journal to be used at the time of making invoice."\
                                 " Select 'Purchase' for Purchase Journal to be used at the time of approving purchase order."\
                                 " Select 'Cash' to be used at the time of making payment."\
                                 " Select 'General' for miscellaneous operations."\
                                 " Select 'Petty Cash' for petty cash operations."\
                                 " Select 'Fund Transfer' for fund transfer operations."\
                                 " Select 'Opening/Closing Situation' to be used at the time of new fiscal year creation or end of year entries generation."),
        
        }
account_journal()