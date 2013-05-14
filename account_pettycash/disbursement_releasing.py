import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
import re

class cash_request_slip(osv.osv):
    _name='cash.request.slip'
    _description = "Cash Request Slip"
    _columns = {
        'name':fields.char('Cash Request Number',size=64, readonly=True),
        'requestor_id':fields.many2one('res.partner','Requestor ID'),
        'request_date':fields.date('Request Date'),
        'pc_id':fields.many2one('account.pettycash','Petty Cash Account'),
        'amount':fields.float('Amount'),
        'state': fields.selection([
            ('draft','Draft'),
            ('approval','For Approval'),
            ('approved','Approved'),
            ('disapproved','Disapproved'),
            ('pending','Pending'),
            ('cancel','Cancelled'),
            ('released','Released')
            ],'Status', select=True, readonly=True),
        'note':fields.text('Other Details'),
        'description':fields.char('Description', size=64),
        
        }
    _defaults={
        'request_date' : lambda *a: time.strftime('%Y-%m-%d'),
        'state':'draft',
        }
    def create(self, cr, uid, vals, context=None):
        vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'cash.request.slip'),
        })
        return super(cash_request_slip, self).create(cr, uid, vals, context)
    def approval(self, cr, uid, ids, context=None):
        for crs in self.browse(cr, uid, ids):
            if crs.amount == 0.00:
                raise osv.except_osv(_('Error!'), _('You are not allowed to request with no amounts.'))
            if crs.pc_id.amount <crs.amount:
                self.write(cr, uid, ids, {'state':'pending'})
            elif crs.pc_id.amount>crs.amount:
                if uid == crs.pc_id.manager_id.id:
                    self.approved(cr, uid, ids, context=None)
                else:
                    self.write(cr, uid, ids, {'state':'approval'})
        return True
    def approved(self, cr, uid, ids, context=None):
        for crs in self.read(cr, uid, ids, context=None):
            values = {
                'crs_id':crs['id'],
                'state':'draft',
                'filled':True,
                }
            disbursement_id = self.pool.get('pettycash.disbursement').create(cr, uid, values)
            pca_read = self.pool.get('account.pettycash').read(cr, uid, crs['pc_id'][0],['currency_id'])
            denoms_search = self.pool.get('denominations').search(cr, uid, [('currency_id','=',pca_read['currency_id'][0])])
            currency = pca_read['currency_id'][1]
            if not denoms_search:
                raise osv.except_osv(_('Error !'), _('%s has no available denominations.Please add them!')%currency)
            if denoms_search:
                for denom in denoms_search:
                    values = {
                        'pd_id':disbursement_id,
                        'name':denom,
                        }
                    self.pool.get('pettycash.denom').create(cr, uid, values)
            self.write(cr, uid, crs['id'], {'state':'approved'})
        return True
    
    def cancel(self, cr, uid, ids, context=None):
        for crs in self.read(cr, uid, ids, context=None):
            releases = self.pool.get('pettycash.disbursement').search(cr, uid, [('crs_id','=',crs['id']),('state','in',['released','received'])])
            if releases:
                raise osv.except_osv(_('Error!'), _('You are not allowed to cancel requests that has been partially released.'))
            if not releases:
                self.write(cr, uid, crs['id'],{'state':'cancel'})
            not_releases = self.pool.get('pettycash.disbursement').search(cr, uid, [('crs_id','=',crs['id']),('state','not in',['released','received'])])
            if not_releases:
                for unreleased in not_releases:
                    self.pool.get('pettycash.disbursement').cancel(cr, uid, unreleased)
            if not not_releases:
                self.write(cr, uid, crs['id'],{'state':'cancel'})
        return True
    
    def disapproved(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'disapproved'})
        return True
cash_request_slip()


class pettycash_disbursement(osv.osv):
    def _get_journal(self, cr, uid, context=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        res = journal_obj.search(cr, uid, [('type', '=', 'disbursement')],limit=1)
        return res and res[0] or False
    
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    _name = 'pettycash.disbursement'
    _description = "Petty Cash Disbursement"
    _columns = {
        'name':fields.char('Disbursement ID',size=64, readonly=True),
        'journal_id':fields.many2one('account.journal','Journal'),
        'pc_id':fields.related('crs_id','pc_id',type='many2one',relation='account.pettycash',store=True, string='Petty Cash Account'),
        'date':fields.date('Disbursement date'),
        'crs_id':fields.many2one('cash.request.slip','Cash Requests Slip'),
        'amount':fields.float('Amount', readonly=True),
        'date':fields.date('Disbursement Date'),
        'period_id':fields.many2one('account.period','Period'),
        'state': fields.selection([
            ('draft','Draft'),
            ('releasing','For Releasing'),
            ('released','In Transit'),
            ('received','Received'),
            ('change_denom','Edit Denominations'),
            ('cancel','Cancelled'),
            ],'Status', select=True),
        }
    _defaults = {
        'period_id':_get_period,
        'state':'draft',
        'journal_id':_get_journal,
        }
    def create(self, cr, uid, vals, context=None):
        vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'pettycash.disbursement'),
        })
        return super(pettycash_disbursement, self).create(cr, uid, vals, context)
    
    def cancel(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state':'cancel'})
    
pettycash_disbursement()

class pettycash_denom(osv.osv):
    _inherit = "pettycash.denom"
    _columns ={
        'pd_id':fields.many2one('pettycash.disbursement','Petty Cash Disbursement ID', ondelete='cascade'),
        }
pettycash_denom()

class pcd(osv.osv):
    _inherit = 'pettycash.disbursement'
    _columns = {
        'denomination_ids':fields.one2many('pettycash.denom','pd_id','Denominations Breakdown', ondelete="cascade"),
        'analytic_id':fields.many2one('account.analytic.account','Debit Account'),
        'partner_id':fields.related('crs_id','requestor_id',type='many2one',relation='res.partner',store=True, string='Entity'),
        'move_id':fields.many2one('account.move','Releasing Entries'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Releasing Journal Items', readonly=True),
        'move_id2':fields.many2one('account.move','Receiving Entries'),
        'move_ids2': fields.related('move_id2','line_id', type='one2many', relation='account.move.line', string='Receiving Journal Items', readonly=True),
        'filled':fields.boolean('Filled'),
        }
    
    def check_disbursements(self, cr, uid, ids,context=None):
        for pcd in self.read(cr, uid, ids, context=None):
            crs = self.pool.get('cash.request.slip').read(cr, uid, pcd['crs_id'][0],['id','amount'])
            pcd_res = self.pool.get('pettycash.disbursement').search(cr, uid, [('id','!=',pcd['id']),('crs_id','=',crs['id'])])
            if not pcd_res: 
                self.pool.get('cash.request.slip').write(cr, uid, crs['id'],{'state':'released'})
            if pcd_res:
                #netsvc.Logger().notifyChannel("pcd_res", netsvc.LOG_INFO, ' '+str(pcd_res))
                released = 0.00
                for pcds in pcd_res:
                    pcd_read = self.pool.get('pettycash.disbursement').read(cr, uid, pcds,['amount'])
                    netsvc.Logger().notifyChannel("pcd_read", netsvc.LOG_INFO, ' '+str(pcd_read))
                    released +=pcd_read['amount']
                if released>crs['amount']:
                    raise osv.except_osv(_('Sobra!'), _('Sobra ka na.'))
                elif released < crs['amount']:
                    raise osv.except_osv(_('Good!'), _('You are good to go.'))
                elif released == crs['amount']:
                    self.pool.get('cash.request.slip').write(cr, uid, crs['id'],{'state':'released'})
        return True
    
    def change_denominations(self, cr, uid, ids, context=None):
        for pcd in self.read(cr, uid, ids, context=None):
            self.write(cr, uid, pcd['id'],{'state':'change_denom'})
        return True
                    
    def get_account(self, cr, uid, ids, context=None):
        amount = 0.00
        ctr = 0
        for pcd in self.read(cr, uid, ids, context=None):
            denoms = self.pool.get('pettycash.denom').search(cr, uid, [('pd_id','=',pcd['id']),('quantity','>','0')])
            pc_read = self.pool.get('account.pettycash').read(cr, uid, pcd['pc_id'][0],['currency_id'])
            pc_curr = pc_read['currency_id'][1]
            if denoms:
                for denom in denoms:
                    denom_reader = self.pool.get('pettycash.denom').read(cr, uid, denom,context=None)
                    pc_denoms = self.pool.get('pettycash.denom').search(cr, uid, [('name','=',denom_reader['name'][0]),('pettycash_id','=',pcd['pc_id'][0]),('quantity','>=',denom_reader['quantity'])])
                    denom_name = denom_reader['name'][1]
                    quantity = denom_reader['quantity']
                    pc_name = pcd['pc_id'][1]
                    if not pc_denoms:
                        raise osv.except_osv(_('Error !'), _('The quantity of %s %s denomination on %s is less than %s! \nPlease create a bill exchange to have the denomination.')%(pc_curr,denom_name,pc_name, quantity))
                    if pc_denoms:
                        denomination = self.pool.get('denominations').read(cr, uid, denom_reader['name'][0],['multiplier'])
                        amount +=denom_reader['quantity'] * denomination['multiplier']
                values = {
                    'amount':amount,
                    'state':'releasing',
                    'name': self.pool.get('ir.sequence').get(cr, uid, 'pettycash.disbursement'),
                    }
                self.write(cr, uid, ids,values)
            if not denoms:
                raise osv.except_osv(_('Error !'), _('You have nothing to disburse! Edit the quantity of the denomination you want to disburse!'))
        return True
    
    def fill_denominations(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=None):
            currency_read = self.pool.get('account.pettycash').read(cr, uid, form['pc_id'][0],['currency_id'])
            if not form['denomination_ids']:
                for denominations in self.pool.get('denominations').search(cr, uid, [('currency_id','=',currency_read['currency_id'][0])]):
                    denom_reader =self.pool.get('denominations').read(cr, uid, denominations,context=None)
                    values = {
                        'name':denom_reader['id'],
                        'pd_id':form['id']
                        }
                    self.pool.get('pettycash.denom').create(cr, uid, values)
            self.write(cr, uid, form['id'],{'filled':True})
        return True
    
    def in_transit(self, cr, uid, ids, context=None):
        for pcd in self.read(cr, uid, ids, context=None):
            for denominations in pcd['denomination_ids']:
                denom_read = self.pool.get('pettycash.denom').read(cr, uid, denominations, context=None)
                if denom_read['quantity']>0.00:
                    for pca_denom in self.pool.get('pettycash.denom').search(cr, uid, [('name','=',denom_read['name'][0]), ('pettycash_id','=',pcd['pc_id'][0])]):
                        pca_denom_read = self.pool.get('pettycash.denom').read(cr, uid, pca_denom,context=None)
                        quantity = pca_denom_read['quantity'] - denom_read['quantity']
                        self.pool.get('pettycash.denom').write(cr, uid, pca_denom, {'quantity':quantity})
            crs_read = self.pool.get('cash.request.slip').read(cr, uid, pcd['crs_id'][0],context=None)
            pc_read = self.pool.get('account.pettycash').read(cr, uid, pcd['pc_id'][0],context=None)
            name = 'Releasing of ' + pcd['name']
            move = {
                'name':name,
                'journal_id':pcd['journal_id'][0],
                'period_id':pcd['period_id'][0],
                'date':pcd['date'],
                'ref':crs_read['name']
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            account_read = self.pool.get('account.account').read(cr, uid, pc_read['account_code'][0],['currency_id','company_currency_id','company_id'])
            company_read = self.pool.get('res.company').read(cr, uid, account_read['company_id'][0],['transit_php','transit_usd'])
            curr_rate = False
            curr_id = False
            amount = False 
            transit_id = False
            if account_read['currency_id']:
                curr_read = self.pool.get('res.currency').read(cr, uid, account_read['currency_id'][0],['rate'])
                curr_rate = curr_read['rate']
                transit_id = company_read['transit_usd'][0]
                curr_id = account_read['currency_id'][0]
                amount = pcd['amount'] / curr_rate
            if not account_read['currency_id']:
                curr_rate = 1.00
                curr_id = account_read['company_currency_id'][0]
                transit_id = company_read['transit_php'][0]
                amount = pcd['amount']
            move_line = {
                'name':'Disbursing Petty Cash',
                'debit': 0.00,
                'credit': amount,
                'account_id': pc_read['account_code'][0],
                'move_id': move_id,
                'journal_id':pcd['journal_id'][0],
                'period_id':pcd['period_id'][0],
                'date':pcd['date'],
                'currency_id':curr_id,
                'amount_currency':pcd['amount'],
                'post_rate':curr_rate,
                }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            analytic_read = self.pool.get('account.analytic.account').read(cr, uid, pcd['analytic_id'][0],['normal_account'])
            move_line = {
                'name':'In Transit Amount',
                'debit': amount,
                'credit': 0.00,
                'account_id': transit_id,
                'move_id': move_id,
                'journal_id':pcd['journal_id'][0],
                'period_id':pcd['period_id'][0],
                'date':pcd['date'],
                'currency_id':curr_id,
                'amount_currency':pcd['amount'],
                'post_rate':curr_rate,
                }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id])
            self.write(cr, uid, pcd['id'],{'state':'released','move_id':move_id})
            self.check_disbursements(cr, uid, [pcd['id']])
        return True
    
    def receive_intransit(self, cr, uid, ids, context=None):
        for pcd in self.read(cr, uid, ids, context=None):
            crs_read = self.pool.get('cash.request.slip').read(cr, uid, pcd['crs_id'][0],context=None)
            pc_read = self.pool.get('account.pettycash').read(cr, uid, pcd['pc_id'][0],context=None)
            name = 'Receiving of ' + pcd['name']
            move = {
                'name':name,
                'journal_id':pcd['journal_id'][0],
                'period_id':pcd['period_id'][0],
                'date':pcd['date'],
                'ref':crs_read['name']
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            account_read = self.pool.get('account.account').read(cr, uid, pc_read['account_code'][0],['currency_id','company_currency_id','company_id'])
            company_read = self.pool.get('res.company').read(cr, uid, account_read['company_id'][0],['transit_php','transit_usd'])
            curr_rate = False
            curr_id = False
            amount = False 
            transit_id = False
            if account_read['currency_id']:
                curr_read = self.pool.get('res.currency').read(cr, uid, account_read['currency_id'][0],['rate'])
                curr_rate = curr_read['rate']
                transit_id = company_read['transit_usd'][0]
                curr_id = account_read['currency_id'][0]
                amount = pcd['amount'] / curr_rate
            if not account_read['currency_id']:
                curr_rate = 1.00
                curr_id = account_read['company_currency_id'][0]
                transit_id = company_read['transit_php'][0]
                amount = pcd['amount']
            move_line = {
                'name':'In Transit Amount',
                'debit': 0.00,
                'credit': amount,
                'account_id': transit_id,
                'move_id': move_id,
                'journal_id':pcd['journal_id'][0],
                'period_id':pcd['period_id'][0],
                'date':pcd['date'],
                'currency_id':curr_id,
                'amount_currency':pcd['amount'],
                'post_rate':curr_rate,
                }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            analytic_read = self.pool.get('account.analytic.account').read(cr, uid, pcd['analytic_id'][0],['normal_account'])
            move_line = {
                'name':'In Transit Amount',
                'debit': amount,
                'credit': 0.00,
                'account_id': analytic_read['normal_account'][0],
                'move_id': move_id,
                'journal_id':pcd['journal_id'][0],
                'period_id':pcd['period_id'][0],
                'date':pcd['date'],
                'currency_id':curr_id,
                'analytic_account_id':pcd['analytic_id'][0],
                'amount_currency':pcd['amount'],
                'post_rate':curr_rate,
                }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id])
            self.write(cr, uid, pcd['id'],{'state':'received','move_id2':move_id})
        return True
    
    def data_get(self, cr, uid, ids, context=None):
        datas = {}
        statements = []
        if context is None:
            context = {}
        for data in self.read(cr, uid, ids, ['id']):
            rec = data['id']
            statements.append(rec)
        datas = {
            'ids':statements,
            'model':'pettycash.disbursement',
            'form':data
            }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'pettycash.disbursement',
            'nodestroy':True,
            'datas': datas,
            }
pcd()