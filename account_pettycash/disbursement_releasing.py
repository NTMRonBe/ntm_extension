import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

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
            if crs.pc_id.amount <crs.amount:
                self.write(cr, uid, ids, {'state':'cancel'})
            elif crs.pc_id.amount>crs.amount:
                self.write(cr, uid, ids, {'state':'approval'})
        return True
    def approved(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'approved'})
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
            ('released','Released'),
            ('cancel','Cancelled'),
            ],'Status', select=True),
        }
    _defaults = {
        'period_id':_get_period,
        'state':'draft',
        'journal_id':_get_journal,
        }
    
pettycash_disbursement()

class pettycash_denom(osv.osv):
    _inherit = "pettycash.denom"
    _columns ={
        'pd_id':fields.many2one('pettycash.disbursement','Petty Cash Disbursement ID'),
        }
pettycash_denom()

class pcd(osv.osv):
    _inherit = 'pettycash.disbursement'
    _columns = {
        'denomination_ids':fields.one2many('pettycash.denom','pd_id','Denominations Breakdown', ondelete="cascade"),
        'analytic_id':fields.many2one('account.analytic.account','Debit Account'),
        }
    
    def check_disbursements(self, cr, uid, ids,context=None):
        for pcd in self.read(cr, uid, ids, context=None):
            crs = self.pool.get('cash.request.slip').read(cr, uid, pcd['crs_id'][0],['id','amount'])
            pcd_res = self.pool.get('pettycash.disbursement').search(cr, uid, [('id','!=',pcd['id']),('crs_id','=',crs['id'])])
            if not pcd_res: 
                self.pool.get('cash.request.slip').write(cr, uid, crs['id'],{'state':'released'})
            if pcd_res:
                netsvc.Logger().notifyChannel("pcd_res", netsvc.LOG_INFO, ' '+str(pcd_res))
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
                    
    def get_account(self, cr, uid, ids, context=None):
        amount = 0.00
        ctr = 0
        account_id = 1
        for pcd in self.read(cr, uid, ids, context=None):
            self.check_disbursements(cr, uid, [pcd['id']])
            netsvc.Logger().notifyChannel("pcd", netsvc.LOG_INFO, ' '+str(pcd))
            crs = self.pool.get('cash.request.slip').read(cr, uid, pcd['crs_id'][0], context=None)
            account_ids = self.pool.get('account.analytic.account').search(cr, uid, [('partner_id','=',crs['requestor_id'][0])])
            if not account_ids:
                raise osv.except_osv(_('Warning!'), _('No Analytic Account for the partner.'))
            if account_ids:
                for account in account_ids:
                    ctr +=1
                    account_id = account
                if ctr > 1:
                    raise osv.except_osv(_('Warning!'), _('You can only define 1 analytic account for a single missionary/project.'))
                elif ctr==1:
                     continue
            for denoms in self.pool.get('pettycash.denom').search(cr, uid, [('pd_id','=',pcd['id'])]):
                denom_reader = self.pool.get('pettycash.denom').read(cr, uid, denoms,context=None)
                denomination = self.pool.get('denominations').read(cr, uid, denom_reader['name'][0],['multiplier'])
                amount +=denom_reader['quantity'] * denomination['multiplier']
            values = {
                'amount':amount,
                'state':'releasing',
                'analytic_id':account_id,
                'name': self.pool.get('ir.sequence').get(cr, uid, 'pettycash.disbursement'),
                }
            self.write(cr, uid, pcd['id'],values)
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
        return True           
    
    def create_entries(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        pc_denom = self.pool.get('pettycash.denom')
        pc_pool = self.pool.get('account.pettycash')
        analytic_pool = self.pool.get('account.analytic.line')
        for pcd in self.read(cr, uid, ids, context=None):
            for denominations in pcd['denomination_ids']:
                denom_read = self.pool.get('pettycash.denom').read(cr, uid, denominations,context=None)
                if denom_read['quantity']>0.00:
                    for pca_denom in self.pool.get('pettycash.denom').search(cr, uid, [('name','=',denom_read['name'][0]), ('pettycash_id','=',pcd['pc_id'][0])]):
                        pca_denom_read = self.pool.get('pettycash.denom').read(cr, uid, pca_denom,context=None)
                        quantity = pca_denom_read['quantity'] - denom_read['quantity']
                        self.pool.get('pettycash.denom').write(cr, uid, pca_denom, {'quantity':quantity})
            crs_read = self.pool.get('cash.request.slip').read(cr, uid, pcd['crs_id'][0],context=None)
            pc_read = pc_pool.read(cr, uid, pcd['pc_id'][0],context=None)
            move = {
                'name':pcd['name'],
                'journal_id':pcd['journal_id'][0],
                'period_id':pcd['period_id'][0],
                'date':pcd['date'],
                'ref':crs_read['name']
                }
            move_id = move_pool.create(cr, uid, move)
            move_line = {
                        'name':pcd['name'],
                        'journal_id':pcd['journal_id'][0],
                        'period_id':pcd['period_id'][0],
                        'date':pcd['date'],
                        'ref':crs_read['name'],
                        'account_id':pc_read['account_code'][0],
                        'debit':pcd['amount'],
                        'move_id':move_id,
                        }
            move_line_pool.create(cr, uid, move_line)
            get_analytic_account = self.pool.get('account.analytic.account').search(cr, uid, [('partner_id','=',crs_read['requestor_id'][0])])
            for analytic_id in get_analytic_account:
                move_line = {
                            'name':crs_read['description'],
                            'journal_id':pcd['journal_id'][0],
                            'period_id':pcd['period_id'][0],
                            'date':pcd['date'],
                            'ref':crs_read['name'],
                            'account_id':pc_read['account_code'][0],
                            'credit':pcd['amount'],
                            'analytic_account_id':analytic_id,
                            'move_id':move_id,
                            }
                move_line_pool.create(cr, uid, move_line)
            self.write(cr, uid, pcd['id'],{'state':'released'})
            self.check_disbursements(cr, uid, [pcd['id']])
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

class account_journal(osv.osv):
    _inherit="account.journal"
    _columns = {
        'type': fields.selection([('sale', 'Sale'),('sale_refund','Sale Refund'), 
                                ('purchase', 'Purchase'), ('purchase_refund','Purchase Refund'),
                                ('transfer','Fund Transfer'), 
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