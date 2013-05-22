import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from compiler.ast import Add

class vehicle_brand(osv.osv):
    _name = 'vehicle.brand'
    _description = "Vehicle Brands"
    _columns = {
        'name':fields.char('Brand',size=32)
        }
vehicle_brand()

class vehicle(osv.osv):
    _name = 'vehicle'
    _description = 'Vehicles'
    _columns = {
        'name':fields.char('Plate Number',size=6),
        'km':fields.float('Number of KM',readonly=True),
        'perkmcharge':fields.float('Per KM charge (less than 150KM)'),
        'perkmcharge150':fields.float('Per KM charge (over 150KM)'),
        'account_id':fields.many2one('account.analytic.account','Vehicle Regional Account'),
        'brand':fields.many2one('vehicle.brand','Brand'),
        'model':fields.char('Model',size=32),
        'color':fields.char('Color',size=32),
        'description':fields.text('Description'),
        }
vehicle()

class vehicle_log(osv.osv):
    def _get_journal(self, cr, uid, context=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        res = journal_obj.search(cr, uid, [('type', '=', 'ved')],limit=1)
        return res and res[0] or False
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    
    _name = 'vehicle.log'
    _description = 'Vehicle Log'
    _columns = {
        'name':fields.char('Control Number',size=64),
        'date':fields.date('Date of Use'),
        'account_id':fields.many2one('account.analytic.account','Charged Account'),
        'start_km':fields.float('Starting KM'),
        'end_km':fields.float('Ending KM'),
        'journal_id':fields.many2one('account.journal','Journal'),
        'period_id':fields.many2one('account.period','Period'),
        'kms':fields.float('Number of KMs'),
        'shared_trip':fields.boolean('Shared Trip'),
        'vehicle_id':fields.many2one('vehicle','Vehicle'),
        'perkmcharge':fields.float('Per KM charge', readonly=True),
        'move_id':fields.many2one('account.move','Journal Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'distribute_type':fields.selection([
                                ('percentage','Percentage'),
                                ('equal','Equally Distributed'),
                                ],'Distribution Type'),
        'state':fields.selection([
                            ('draft','Draft'),
                            ('confirm','Confirm'),
                            ('distributed','Distribute'),
                            ],'State'),
        'details':fields.text('Trip Details'),
        'total':fields.float('Total Distributed Amount', readonly=True),
        }
    _defaults = {
        'date':lambda *a: time.strftime('%Y-%m-%d'),
        'state':'draft',
        'journal_id':_get_journal,
        'period_id':_get_period,
        }
    
    _order = 'date asc'
    
    def create(self, cr, uid, vals, context=None):
        vals.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'ved'),
        })
                
        return super(vehicle_log, self).create(cr, uid, vals, context)
       
    def onchange_vehicle(self, cr, uid, ids, vehicle_id=False,shared_trip=False):
        result = {}
        if vehicle_id and not shared_trip:
            vehicle_read= self.pool.get('vehicle').read(cr, uid, vehicle_id, ['km','perkmcharge150','perkmcharge'])
            end_km = False
            for trips in self.pool.get('vehicle.log').search(cr, uid, [('vehicle_id','=',vehicle_id),('state','=','distributed')],limit=1, order='end_km desc'):
                trip_read = self.pool.get('vehicle.log').read(cr, uid, trips,['end_km'])
                end_km = trip_read['end_km']
                self.onchange_ending(cr, uid, ids, end_km)
            result = {'value':{
                        'start_km':end_km,
                        }
                }
        return result
    
    def onchange_ending(self, cr, uid, ids, end_km=False):
        result = {}
        if end_km:
            for log in self.read(cr, uid, ids, context=None):
                kms = end_km - log['start_km']
                vehicle_read = self.pool.get('vehicle').read(cr, uid, log['vehicle_id'][0],['perkmcharge','perkmcharge150'])
                charge=0.00
                if kms > 150.00:
                    charge=vehicle_read['perkmcharge150']
                elif kms<151 and kms>0:
                    charge=vehicle_read['perkmcharge']
                elif kms<1:
                    raise osv.except_osv(_('Error!'), _(''))
                result = {'value':{
                            'kms':kms,
                            'perkmcharge':charge,
                            }
                    }
        return result
    
    def write(self,cr, uid,ids,vals, context=None):
        if 'end_km' in vals:
            for log in self.read(cr, uid, ids, context=None):
                kms = vals['end_km'] - log['start_km']
                vehicle_read = self.pool.get('vehicle').read(cr, uid, log['vehicle_id'][0],['perkmcharge','perkmcharge150'])
                charge=0.00
                if kms > 150.00:
                    charge=vehicle_read['perkmcharge150']
                elif kms<151 and kms>0:
                    charge=vehicle_read['perkmcharge']
                elif kms<1:
                    raise osv.except_osv(_('Error!'), _(''))
                vals['kms']=kms
                vals['perkmcharge']=charge
        return super(vehicle_log,self).write(cr, uid,ids, vals,context=None)
    
    def cancel(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state':'cancel'})
    
    def confirm(self, cr, uid, ids, context=None):
        for log in self.read(cr, uid, ids, context=None):
            if log['shared_trip']:
                self.confirm_shared(cr, uid, ids)
            elif not log['shared_trip']:
                total = log['kms'] * log['perkmcharge']
                self.write(cr, uid, ids, {'total':total,'state':'confirm'})
        return True
    
    def confirm_shared(self, cr, uid, ids, context=None):
        for log in self.read(cr, uid, ids, context=None):
            total_km = 0.00
            total_amount = 0.00
            for trip_id in self.pool.get('vehicle.log.shared').search(cr, uid, [('log_id','=',log['id'])]):
                trip_read = self.pool.get('vehicle.log.shared').read(cr, uid, trip_id,context=None)
                kms = trip_read['end_km'] - trip_read['start_km']
                total_km += kms
            vehicle_read = self.pool.get('vehicle').read(cr, uid, log['vehicle_id'][0],['perkmcharge','perkmcharge150'])
            charge=0.00
            if total_km > 150.00:
                charge=vehicle_read['perkmcharge150']
            elif total_km<151 and total_km>0:
                charge=vehicle_read['perkmcharge']
            for trip_id in self.pool.get('vehicle.log.shared').search(cr, uid, [('log_id','=',log['id'])]):
                trip_read = self.pool.get('vehicle.log.shared').read(cr, uid, trip_id,context=None)
                print trip_read
                kms = trip_read['end_km'] - trip_read['start_km']
                amount = 0.00
                if trip_read['shared']:
                    amount = ((kms * trip_read['percentage'])/100) * charge
                elif not trip_read['shared']:
                    amount = kms * charge
                total_amount +=amount
                self.pool.get('vehicle.log.shared').write(cr, uid, trip_id,{'amount':amount,'kms':kms})
            vals = {
                'perkmcharge':charge,
                'total':total_amount,
                'state':'confirm',
                }
            self.write(cr, uid, ids, vals)
        return True
                    
                
    
    def distribute(self, cr, uid, ids, context=None):
        for log in self.read(cr, uid, ids, context=None):
            journal_id = log['journal_id'][0]
            period_id = log['period_id'][0]
            date = log['date']
            move = {
                'name':log['name'],
                'journal_id':journal_id,
                'period_id':period_id,
                'date':date,
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            if not log['shared_trip']:
                amount = log['total']
                vehicle_read = self.pool.get('vehicle').read(cr, uid, log['vehicle_id'][0],['account_id'])
                analytic_acc_v = self.pool.get('account.analytic.account').read(cr, uid, vehicle_read['account_id'][0],['normal_account'])
                check_curr = self.pool.get('account.account').read(cr, uid, analytic_acc_v['normal_account'][0],['company_currency_id'])
                user_read = self.pool.get('account.analytic.account').read(cr, uid, log['account_id'][0],['normal_account'])
                move_line = {
                        'name':'Vehicle Income',
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':analytic_acc_v['normal_account'][0],
                        'credit':amount,
                        'analytic_account_id':vehicle_read['account_id'][0],
                        'date':date,
                        'ref':log['name'],
                        'move_id':move_id,
                        'amount_currency':amount,
                        'currency_id':check_curr['company_currency_id'][0],
                        }
                self.pool.get('account.move.line').create(cr, uid, move_line)
                move_line = {
                        'name':'Expense',
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':user_read['normal_account'][0],
                        'debit':amount,
                        'analytic_account_id':log['account_id'][0],
                        'date':date,
                        'ref':log['name'],
                        'move_id':move_id,
                        'amount_currency':amount,
                        'currency_id':check_curr['company_currency_id'][0],
                    }
                self.pool.get('account.move.line').create(cr, uid, move_line)
                self.pool.get('account.move').post(cr, uid, [move_id])
                self.write(cr, uid, ids, {'move_id':move_id,'state':'distributed'})
        return True
        
vehicle_log()

class vehicle_trips(osv.osv):
    _inherit = 'vehicle'
    _columns = {
        'trip_ids':fields.one2many('vehicle.log','vehicle_id','Trips'),
        }
vehicle_trips()

class vehicle_log_shared(osv.osv):
    _name = 'vehicle.log.shared'
    _description = "Expense Distribution"
    _columns = {
        'name': fields.related('account_id','name', type='char',size=64,string='Account Name', readonly=True),
        'log_id':fields.many2one('vehicle.log','Vehicle Log ID',ondelete='cascade'),
        'account_id':fields.many2one('account.analytic.account','Charged Account'),
        'amount':fields.float('Charge Amount'),
        'start_km':fields.float('Starting KM'),
        'kms':fields.float('Total KMS'),
        'end_km':fields.float('Ending KM'),
        'shared':fields.boolean('Shared'),
        'share_with':fields.many2one('vehicle.log.shared','Shared with?'),
        'percentage':fields.float('Percentage'),
        'main_trip':fields.boolean('Main Trip'),
        }
    _order = 'start_km asc'
vehicle_log_shared()

class vlog(osv.osv):
    _inherit = 'vehicle.log'
    _columns = {
        'shared_ids':fields.one2many('vehicle.log.shared','log_id','Expense Distribution')
        }
vlog()


class add_vehicle(osv.osv_memory):
    _name = 'add.vehicle'
    _columns = {
        'account_id':fields.many2one('account.analytic.account','Charged Account', required=True),
        'start_km':fields.float('Starting KM'),
        'end_km':fields.float('Ending KM', required=True),
        'shared':fields.boolean('Shared'),
        'share_with':fields.many2one('vehicle.log.shared','Shared with?'),
        'percentage':fields.float('Percentage'),
        'main_trip':fields.boolean('Main Trip'),
        }
    def data_save(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=context):
            print form
            share_with = False
            shared = False
            percentage = 0.00
            main_trip=False
            if form['shared']:
                shared=True
                main_trip=form['main_trip']
                share_with = form['share_with']
                print share_with
                percentage = form['percentage']
                if share_with:
                    shared_with_read = self.pool.get('vehicle.log.shared').read(cr, uid, share_with,['log_id','main_trip','shared','percentage'])
                    main_trip_share = self.pool.get('vehicle.log.shared').search(cr, uid, [('share_with','=',share_with)])
                    total_percentage=shared_with_read['percentage'] + percentage
                    for trips in main_trip_share:
                        trip_read = self.pool.get('vehicle.log.shared').read(cr, uid, trips,['percentage'])
                        total_percentage += trip_read['percentage']
                    if total_percentage > 100:
                        raise osv.except_osv(_('Error!'), _('Total percentage for the main trip together with it\'s subtrips is greater than 100\%!'))
                    if shared_with_read['log_id'][0]!=context['active_id']:
                        raise osv.except_osv(_('Error!'), _('Share with account is not with the same log!'))
            vals = {
                'account_id':form['account_id'],
                'end_km':form['end_km'],
                'start_km':form['start_km'],
                'log_id':context['active_id'],
                'percentage':percentage,
                'shared':shared,
                'share_with':share_with,
                'main_trip':main_trip,
                }
            self.pool.get('vehicle.log.shared').create(cr, uid, vals)
            self.pool.get('vehicle.log').write(cr, uid, context['active_id'],{'log_id':context['active_id']})
        return {'type': 'ir.actions.act_window_close'}
    
    def onchange_sharewith(self, cr, uid, ids, share_with=False,context=None):
        result = {}
        if share_with:
            for form in self.read(cr, uid, ids, context=context):
                share_read = self.pool.get('vehicle.log.shared').read(cr, uid, form['share_with'],['end_km','start_km'])
                result = {'values':{
                        'end_km':share_read['end_km'],
                        'start_km':share_read['start_km'],
                        }
                    }
        return result
add_vehicle()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,