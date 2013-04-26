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
    
    _inherit = 'res.partner'
    _description = 'Partner'
    _columns = {
        'partner_dict':fields.one2many('ntm.res.partner.extension','partner_id','Dictionary'),
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
            'post_amount':"COALESCE(SUM(l.amount_currency), 0) as post_amount",
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
        'post_amount': fields.function(__compute, digits_compute=dp.get_precision('Account'), method=True, string='Posting Amount', multi='balance'),
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