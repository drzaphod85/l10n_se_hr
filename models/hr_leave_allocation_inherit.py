# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date

class HrLeaveAllocationInherit(models.Model):
    _inherit = 'hr.leave.allocation'

    # --- Fält och metoder från hr_vacation_leave_inherit.py ---
    is_swedish_vacation = fields.Boolean(
        string='Swedish Vacation Allocation', # Tydligare namn?
        compute='_compute_is_swedish_vacation',
        store=True, # Bra att lagra för filtrering
        readonly=True # Beräknas från typen
    )
    vacation_year = fields.Char(
        string='Vacation Year',
        compute='_compute_vacation_year',
        store=True, # Bra att lagra för sökning/gruppering
        help="Format YYYY/YYYY, e.g., 2024/2025"
    )

    @api.depends('holiday_status_id')
    def _compute_is_swedish_vacation(self):
        swedish_vacation_type = self.env.ref('l10n_se_hr.holiday_status_swedish_vacation', raise_if_not_found=False)
        for allocation in self:
            if swedish_vacation_type:
                 allocation.is_swedish_vacation = allocation.holiday_status_id.id == swedish_vacation_type.id
            else:
                 allocation.is_swedish_vacation = False

    @api.depends('date_from') # Eller ska den baseras på när allokeringen gäller? Ofta inte satt.
    def _compute_vacation_year(self):
        # Denna logik kan vara problematisk om date_from inte sätts/används konsekvent
        # Kanske bättre att sätta manuellt eller via en wizard?
        for allocation in self:
            # Försök använda create_date som fallback? Eller sätt manuellt?
            ref_date = allocation.date_from or fields.Date.context_today(allocation) # Fallback till idag

            year = ref_date.year
            month = ref_date.month
            if month < 4:
                allocation.vacation_year = f"{year-1}/{year}"
            else:
                allocation.vacation_year = f"{year}/{year+1}"