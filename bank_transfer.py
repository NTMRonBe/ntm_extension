import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from datetime import datetime
from dateutil.relativedelta import relativedelta
from operator import itemgetter    
    
class bank_transfer_schedule(osv.osv):
    _name = "bank.transfer.schedule"
    _description = "Bank Transfer Schedule"
    _columns = {
        'name':fields.char('Schedule ID',size=32),
        'company_bank_id':fields.many2one('res.partner.bank','Account #',domain=[('ownership','=','company')]),
        'company_bank_name':fields.related('company_bank_id','bank', type='many2one',relation="res.bank", string='Company Name', readonly=True,store=True),
        'company_acc_name':fields.related('company_bank_id','owner_name', type='char',size=64, string='Account Name', readonly=True,store=True),
        'entity_bank_id':fields.many2one('res.partner.bank','Account #',domain=[('ownership','=','entity')]),
        'entity_bank_name':fields.related('entity_bank_id','owner_name', type='char',size=64, string='Account Name', readonly=True,store=True),
        'account_id':fields.many2one('account.analytic.account','Recipient Name'),
        'account_name':fields.related('account_id','name', type='char',size=64, string='Account Name', readonly=True,store=True),
        'date_start': fields.date('Start Date', required=True),
        'period_total': fields.integer('Number of Periods', required=True),
        'period_nbr': fields.integer('Period', required=True),
        'period_type': fields.selection([('day','days'),('month','month'),('year','year'),('bimonthly','bimonthly')], 'Period Type', required=True),
        'state': fields.selection([('draft','Draft'),('running','Running'),('done','Done')], 'State', required=True, readonly=True),
        'amount':fields.float('Amount'),
        'remarks':fields.text('Remarks'),
    }
    _defaults = {
        'date_start': lambda *a: time.strftime('%Y-%m-%d'),
        'period_type': 'month',
        'period_total': 12,
        'period_nbr': 1,
        'state': 'draft',
    }
    def state_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'draft'})
        return False

    def check(self, cr, uid, ids, context=None):
        todone = []
        for sub in self.browse(cr, uid, ids, context=context):
            ok = True
            for line in sub.lines_id:
                if not line.move_id.id:
                    ok = False
                    break
            if ok:
                todone.append(sub.id)
        if todone:
            self.write(cr, uid, todone, {'state':'done'})
        return False

    def remove_line(self, cr, uid, ids, context=None):
        toremove = []
        for sub in self.browse(cr, uid, ids, context=context):
            for line in sub.lines_id:
                toremove.append(line.id)
        if toremove:
            self.pool.get('bank.transfer.request').unlink(cr, uid, toremove)
        self.write(cr, uid, ids, {'state':'draft'})
        return False

    def compute(self, cr, uid, ids, context=None):
        for sub in self.browse(cr, uid, ids, context=context):
            ds = sub.date_start
            for i in range(sub.period_total):
                request_id = self.pool.get('bank.transfer.request').create(cr, uid, {
                    'date': ds,
                    'schedule_id': sub.id,
                    'company_bank_id':sub.company_bank_id.id,
                    'entity_bank_id':sub.entity_bank_id.id,
                    'account_id':sub.account_id.id,
                    'remarks':sub.remarks,
                    'amount':sub.amount,
                    'state':'confirm',
                })
                if sub.period_type=='day':
                    ds = (datetime.strptime(ds, '%Y-%m-%d') + relativedelta(days=sub.period_nbr)).strftime('%Y-%m-%d')
                if sub.period_type=='month':
                    ds = (datetime.strptime(ds, '%Y-%m-%d') + relativedelta(months=sub.period_nbr)).strftime('%Y-%m-%d')
                if sub.period_type=='bimonthly':
                    ds = (datetime.strptime(ds, '%Y-%m-%d') + relativedelta(weeks=+2)).strftime('%Y-%m-%d')
                if sub.period_type=='year':
                    ds = (datetime.strptime(ds, '%Y-%m-%d') + relativedelta(years=sub.period_nbr)).strftime('%Y-%m-%d')
        self.write(cr, uid, ids, {'state':'running'})
        return True
bank_transfer_schedule()

class bank_transfer_request(osv.osv):
    _name = "bank.transfer.request"
    _description = "Bank Transfer Requests"
    _columns = {
        'name':fields.char('Request ID',size=32),
        'schedule_id': fields.many2one('bank.transfer.schedule', select=True, ondelete='cascade'),
        'company_bank_name':fields.related('company_bank_id','bank', type='many2one',relation="res.bank", string='Account Name', readonly=True,store=True),
        'company_bank_id':fields.many2one('res.partner.bank','Company Bank Account',domain=[('ownership','=','company')]),
        'company_acc_name':fields.related('company_bank_id','owner_name', type='char',size=64, string='Account Name', readonly=True,store=True),
        'entity_bank_id':fields.many2one('res.partner.bank','Account #',domain=[('ownership','=','entity')]),
        'entity_bank_name':fields.related('entity_bank_id','owner_name', type='char',size=64, string='Account Name', readonly=True,store=True),
        'account_id':fields.many2one('account.analytic.account','Name Account'),
        'account_name':fields.related('account_id','name', type='char',size=64, string='Account Name', readonly=True,store=True),
        'date':fields.date('Effective Date'),
        'remarks':fields.text('Remarks'),
        'amount':fields.float('Amount'),
        'is_special':fields.boolean('Special Request?'),
        'state':fields.selection([
                            ('confirm','Confirm'),
                            ('cancel','Cancelled'),
                            ],'State'),
    }
    
    def create(self, cr, uid, vals, context=None):
        vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'bank.transfer.request'),
        })
        return super(bank_transfer_request, self).create(cr, uid, vals, context)
    
    def confirm(self, cr, uid, ids, context=None):
        for btr in self.read(cr, uid, ids, context=None):
            self.write(cr, uid, ids, {'state':'confirm'})
        return True
    
    def cancel(self, cr, uid, ids, context=None):
        for btr in self.read(cr, uid, ids, context=None):
            self.write(cr, uid, ids, {'state':'cancel'})
        return True

bank_transfer_request()

class btr(osv.osv):
    _inherit = 'bank.transfer.schedule'
    _columns = {
        'lines_id': fields.one2many('bank.transfer.request', 'schedule_id', 'Subscription Lines')
        }
btr()

class bank_transfer(osv.osv):
    
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    
    _name = 'bank.transfer'
    _description = 'Bank Transfer'
    _columns = {
        'name':fields.char('Transfer ID',size=64,readonly=True),
        'date':fields.date('Transfer Date'),
        'handler':fields.many2one('res.users','Handler'),
        'journal_id':fields.many2one('account.journal','Bank Journal'),
        'period_id':fields.many2one('account.period','Transfer Period'),
        'ref':fields.char('Reference',size=64),
        'state':fields.selection([
                            ('draft','Draft'),
                            ('done','Transferred'),
                            ],'State'),
        'move_id':fields.many2one('account.move','Move Name'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'amount':fields.float('Total Amount'),
        }
    _defaults = {
            'state':'draft',
            'name':'NEW',
            'period_id':_get_period,
            'date' : lambda *a: time.strftime('%Y-%m-%d'),
            'handler' : lambda cr, uid, id, c={}: id,
            }
bank_transfer()

class bank_transfer_line(osv.osv):
    _name = 'bank.transfer.line'
    _description = 'Bank Transfer Lines'
    _columns = {
        'transfer_id':fields.many2one('bank.transfer','Transfer ID',ondelete='cascade'),
        'partner_id':fields.many2one('res.partner','Partner', required=True),
        'account_number':fields.many2one('res.partner.bank','Bank Account', required=True),
        'analytic_id':fields.many2one('account.analytic.account','Account', required=True),
        'amount':fields.float('Amount', required=True),
        'type':fields.selection([
                            ('savings','Savings'),
                            ('checking','Checking'),
                            ],'Type', required=True),
        }
bank_transfer_line()

class btl_add(osv.osv_memory):
    _name = 'bank.transfer.line.add'
    _columns = {
        'partner_id':fields.many2one('res.partner','People/Project', required=True),
        'account_number':fields.many2one('res.partner.bank','Bank Account', required=True),
        'analytic_id':fields.many2one('account.analytic.account','Account', required=True),
        'amount':fields.float('Amount', required=True),
        'type':fields.selection([
                            ('savings','Savings'),
                            ('checking','Checking'),
                            ],'Type', required=True),
        }
    def onchange_partner(self, cr, uid, ids, partner_id=False):
        result = {}
        acc_account = False
        if partner_id:
            partner_read = self.pool.get('res.partner').read(cr, uid, partner_id,['name'])
            partner_name = partner_read['name']
            bank_ids = self.pool.get('res.partner.bank').search(cr, uid, [('partner_id','=',partner_id)])
            if not bank_ids:
                raise osv.except_osv(_('Error !'), _('%s has no bank account defined. Please define one.')%partner_name)
            acc_ids = self.pool.get('account.analytic.account').search(cr, uid, [('partner_id','=',partner_id)])
            if not acc_ids:
                raise osv.except_osv(_('Error !'), _('%s has no analytic account defined. Please define one.')%partner_name)
            elif acc_ids:
                acc_ctr = 0
                for acc_id in acc_ids:
                    acc_ctr += 1
                    acc_account = acc_id
                if acc_ctr > 1:
                    raise osv.except_osv(_('Error !'), _('%s has %s bank accounts defined. Multiple bank accounts are not allowed')%(partner_name, acc_ctr))
                elif acc_ctr==1:
                    acc_account = acc_account
            result = {'value':{
                    'analytic_id':acc_account,
                    }
                }
        elif not partner_id:
            result = {'value':{
                    'analytic_id':False,
                    }
                }
        return result
    
    def add_account(self, cr, uid, ids, context=None):
        for add in self.read(cr, uid, ids, context=context):
            if add['amount']<1.00:
                raise osv.except_osv(_('Error !'), _('You can not have 0.00 as the amount for transfer!'))
            elif add['amount']>0.00:
                for id in context['active_ids']:
                    lines = self.pool.get('bank.transfer.line').search(cr, uid, [('partner_id','=',add['partner_id']),
                                                                                 ('account_number','=',add['account_number']),
                                                                                 ('transfer_id','=',id)])
                    if lines:
                        raise osv.except_osv(_('Error !'), _('The account is already included!'))
                    elif not lines:
                        values = {
                            'partner_id':add['partner_id'],
                            'account_number':add['account_number'],
                            'analytic_id':add['analytic_id'],
                            'amount':add['amount'],
                            'type':add['type'],
                            'transfer_id':id,
                            }
                        self.pool.get('bank.transfer.line').create(cr, uid,values)
        return {'type': 'ir.actions.act_window_close'}
                    
btl_add()
    

class bt(osv.osv):
    _inherit = 'bank.transfer'
    _columns = {
        'savings_ids':fields.one2many('bank.transfer.line','transfer_id','Transfer Lines',domain=[('type','=','savings')]),
        'checking_ids':fields.one2many('bank.transfer.line','transfer_id','Transfer Lines',domain=[('type','=','checking')]),
        }
    
    def def_name(self, cr, uid, ids, context=None):
        for bt in self.read(cr, uid, ids, context=None):
            if bt['name']=='NEW':
                values = {
                        'name':self.pool.get('ir.sequence').get(cr, uid, 'bank.transfer'),
                        }
                self.write(cr, uid, bt['id'],values)
            elif bt['name']!='NEW':
                return True
        return True
    
    def complete(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        journal_pool = self.pool.get('account.journal')
        move_line_pool = self.pool.get('account.move.line')
        line_pool = self.pool.get('bank.transfer.line')
        analytic_pool = self.pool.get('account.analytic.account')
        for bt in self.read(cr, uid, ids, context=None):
            move = {
                        'journal_id':bt['journal_id'][0],
                        'period_id':bt['period_id'][0],
                        'date':bt['date'],
                        'ref':bt['ref'],
                        }
            amount = 0.00
            move_id = move_pool.create(cr, uid, move)
            for lines in bt['savings_ids']:
                read_line = line_pool.read(cr, uid, lines, context=None)
                analytic_read = analytic_pool.read(cr, uid, read_line['analytic_id'][0],context=None)
                if analytic_read['normal_account']:
                    credit = {
                        'name':read_line['account_number'][1],
                        'journal_id':bt['journal_id'][0],
                        'period_id':bt['period_id'][0],
                        'date':bt['date'],
                        'account_id':analytic_read['normal_account'][0],
                        'debit':read_line['amount'],
                        'analytic_account_id':read_line['analytic_id'][0],
                        'move_id':move_id,
                    }
                    move_line_pool.create(cr, uid, credit)
                    amount +=read_line['amount']
            for lines in bt['checking_ids']:
                read_line = line_pool.read(cr, uid, lines, context=None)
                analytic_read = analytic_pool.read(cr, uid, read_line['analytic_id'][0],context=None)
                if analytic_read['normal_account']:
                    credit = {
                        'name':read_line['account_number'][1],
                        'journal_id':bt['journal_id'][0],
                        'period_id':bt['period_id'][0],
                        'date':bt['date'],
                        'account_id':analytic_read['normal_account'][0],
                        'debit':read_line['amount'],
                        'analytic_account_id':read_line['analytic_id'][0],
                        'move_id':move_id,
                    }
                    move_line_pool.create(cr, uid, credit)
                    amount +=read_line['amount']
            journal_read = journal_pool.read(cr, uid, bt['journal_id'][0],['default_debit_account_id','bank_id'])
            debit = {
                        'name':bt['ref'],
                        'journal_id':bt['journal_id'][0],
                        'period_id':bt['period_id'][0],
                        'date':bt['date'],
                        'account_id':journal_read['default_debit_account_id'][0],
                        'credit':amount,
                        'move_id':move_id,
                        }
            move_line_pool.create(cr, uid, debit)
            values = {
                'state':'done',
                'move_id':move_id,
                'amount':amount,
                }
            self.def_name(cr, uid, [bt['id']])
            self.write(cr, uid, [bt['id']],values)
        return True       
    
    def cancel(self, cr, uid, ids, context=None):
        for bt in self.read(cr, uid, ids, context=None):
            move_id = bt['move_id'][0]
            self.pool.get('account.move').unlink(cr, uid, [move_id])
        return self.write(cr, uid, ids, {'state':'draft'})
    
    def data_get(self, cr, uid, ids, context=None):
        datas = {}
        statements = []
        if context is None:
            context = {}
        for data in self.read(cr, uid, ids, ['id']):
            rec = data['id']
            attachments = self.pool.get('ir.attachment').search(cr, uid, [('res_model','=','bank.transfer'),('res_id','=',rec)])
            self.pool.get('ir.attachment').unlink(cr, uid, attachments)
            statements.append(rec)
        datas = {
            'ids':statements,
            'model':'bank.transfer',
            'form':data
            }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'bank.transfer',
            'nodestroy':True,
            'datas': datas,
            }
                
            
            
bt()

class res_partner_check_numbers(osv.osv):
    _name = 'res.partner.check.numbers'
    _description = "Check Sequences"
    _columns = {
        'bank_account_id':fields.many2one('res.partner.bank','Bank Account', ondelete='cascade'),
        'name':fields.integer('Check Number'),
        'state':fields.selection([
                            ('available','Available'),
                            ('assigned','Assigned'),
                            ('released','Released'),
                            ('cleared','Cleared'),
                            ],'Check State'),
        }
res_partner_check_numbers()

class res_partner_bank(osv.osv):
    _inherit = 'res.partner.bank'
    _columns = {
        'check_numbers':fields.one2many('res.partner.check.numbers','bank_account_id','Check Numbers'),
        'partner_id': fields.many2one('res.partner', 'People/Project', ondelete='cascade', select=True),
        'bank': fields.many2one('res.bank', 'Bank'),
        'ownership':fields.selection([
                                 ('company','Company Account'),
                                 ('entity','Entity Account')
                                 ],'Ownership'),
        'type':fields.selection([
                            ('savings','Savings'),
                            ('checking','Checking'),
                            ],'Type', required=True),
        'journal_id':fields.many2one('account.journal','Bank Journal'),
        'account_id':fields.many2one('account.account','Book Account Name'),
        'transit_id':fields.many2one('account.account','Transit Account'),
		'balance':fields.related('account_id','post_amount', type='float', string='Bank Balance', readonly=True),
        'currency_id': fields.many2one('res.currency','Currency'),
        'starting_sequence':fields.integer('Starting Sequence'),
        'ending_sequence':fields.integer('Ending Sequence'),
        }
    
    def onchange_journal(self, cr, uid, ids, journal_id=False):
        result = {}
        if journal_id:
            journal_read = self.pool.get('account.journal').read(cr, uid, journal_id, ['default_debit_account_id'])
            account_id = journal_read['default_debit_account_id'][0]
            account_read = self.pool.get('account.account').read(cr, uid, account_id,['currency_id','company_currency_id'])
            curr_id = False
            if not account_read['currency_id']:
                curr_id = account_read['company_currency_id'][0]
            if account_read['currency_id']:
                curr_id = account_read['currency_id'][0]
            result = {'value':{
                            'account_id':account_id,
                            'currency_id':curr_id,
                            }} 
        return result
res_partner_bank()

class check_sequence_wizard(osv.osv_memory):
    _name = 'check.sequence.wizard'
    _columns = {
        'start_sequence':fields.integer('Start Sequence'),
        'end_sequence':fields.integer('Start Sequence'),
        }
    def add_sequence(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=None):
            print context
            if form['start_sequence']<form['end_sequence']:
                seq_search = self.pool.get('res.partner.check.numbers').search(cr, uid, [('name','=',form['start_sequence'])])
                if not seq_search:
                    seq_search = self.pool.get('res.partner.check.numbers').search(cr, uid, [('name','=',form['end_sequence'])])
                    if not seq_search:
                        check_range = form['end_sequence']-form['start_sequence']
                        start = form['start_sequence']
                        end = form['end_sequence']
                        end = end+1
                        ctr=0.00
                        for x in xrange(start,end):
                            print x
                            if x<=form['end_sequence']:
                                vals = {
                                    'bank_account_id':context['active_id'],
                                    'name':x,
                                    'state':'available',
                                    }
                                self.pool.get('res.partner.check.numbers').create(cr, uid, vals)
                            elif x>form['end_sequence']:
                                break
            elif form['start_sequence']>form['end_sequence']:
                raise osv.except_osv(_('Error !'), _('Start sequence greater than end sequence'))
        return {'type': 'ir.actions.act_window_close'}
check_sequence_wizard()
'''
class bank_transfer_wizard(osv.osv_memory):
    _name = 'bank.transfer.wizard'
    _columns = {
        ''
        }
'''