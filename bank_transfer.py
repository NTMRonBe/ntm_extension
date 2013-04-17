import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

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
        'partner_id':fields.many2one('res.partner','Partner', required=True),
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

class res_partner_bank(osv.osv):
    _inherit = 'res.partner.bank'
    _columns = {
        'partner_id': fields.many2one('res.partner', 'Partner', ondelete='cascade', select=True),
        'bank': fields.many2one('res.bank', 'Bank'),
        'ownership':fields.selection([
                                 ('company','Company Account'),
                                 ('entity','Entity Account')
                                 ],'Ownership'),
        'type':fields.selection([
                            ('savings','Savings'),
                            ('checking','Checking'),
                            ],'Type', required=True),
        }
res_partner_bank()


class account_journal(osv.osv):
    _inherit = 'account.journal'
    _columns = {
        'bank_id':fields.many2one('res.partner.bank','Bank'),
        }
account_journal()