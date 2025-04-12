from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_update_regions_municipalities(self):
        self.env['municipality.updater'].update_municipalities()