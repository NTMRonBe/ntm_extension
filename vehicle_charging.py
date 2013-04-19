import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class vehicle(osv.osv):
    _name = 'vehicle'
    _description = 'Vehicles'
    _columns = {
        'name':fields.char('Plate Number',size=6),
        'km':fields.float('Number of KM',readonly=True),
        'perkmcharge':fields.float('Per KM charge (less than 150KM)'),
        'perkmcharge150':fields.float('Per KM charge (over 150KM)'),
        'account_id':fields.many2one('account.account','Vehicle Account'),
        }
vehicle()

class vehicle_log(osv.osv):
    _name = 'vehicle.log'
    _description = 'Vehicle Log'
    _columns = {
        'name':fields.char('Control Number',size=64),
        'date':fields.date('Date of Use'),
        'partner_id':fields.many2one('res.partner','Missionary'),
        'start_km':fields.float('Starting KM'),
        'end_km':fields.float('Ending KM'),
        'kms':fields.float('Number of KMs'),
        'shared':fields.boolean('Shared Trip'),
        'vehicle_id':fields.many2one('vehicle','Vehicle'),
        'distributed':fields.boolean('Distributed', readonly=True),
        'perkmcharge':fields.float('Per KM charge (less than 150KM)'),
        'perkmcharge150':fields.float('Per KM charge (over 150KM)'),
        }
       
    def onchange_vehicle(self, cr, uid, ids, vehicle_id=False):
        result = {}
        if vehicle_id:
            vehicle_read= self.pool.get('vehicle').read(cr, uid, vehicle_id, ['km','perkmcharge150','perkmcharge'])
            netsvc.Logger().notifyChannel("vehicle_read", netsvc.LOG_INFO, ' '+str(vehicle_read))
            result = {'value':{
                        'start_km':vehicle_read['km'],
                        'perkmcharge':vehicle_read['perkmcharge'],
                        'perkmcharge150':vehicle_read['perkmcharge150']
                        }
                }
        return result
vehicle_log()

class vehicle_log_shared(osv.osv):
    _name = 'vehicle.log.shared'
    _description = "Expense Distribution"
    _columns = {
        'log_id':fields.many2one('vehicle.log','Vehicle Log ID',ondelete='cascade'),
        'partner_id':fields.many2one('res.partner','Missionary'),
        'percentage':fields.float('Usage Percentage'),
        }
vehicle_log_shared()

class vlog(osv.osv):
    _inherit = 'vehicle.log'
    _columns = {
        'shared_ids':fields.one2many('vehicle.log.shared','log_id','Expense Distribution')
        }
vlog()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,