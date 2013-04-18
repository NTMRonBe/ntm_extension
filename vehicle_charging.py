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
        }
vehicle()

class vehicle_log(osv.osv):
    _name = 'vehicle.log'
    _description = 'Vehicle Log'
    _columns = {
        'name':fields.char('Control Number',size=64),
        'date':fields.date('Date of Use'),
        'start_km':fields.float('Starting KM'),
        'end_km':fields.float('Ending KM'),
        'kms':fields.float('Number of KMs'),
        'shared':fields.boolean('Shared Trip'),
        'vehicle_id':fields.many2one('vehicle','Vehicle'),
        'distributed':fields.boolean('Distributed'),
        }
vehicle_log()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,