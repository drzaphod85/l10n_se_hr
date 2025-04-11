from odoo import models, fields

class ResRegion(models.Model):
    _name = 'res.region'
    _description = 'Swedish Region'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    municipality_ids = fields.One2many('res.municipality', 'region_id', string='Municipalities')