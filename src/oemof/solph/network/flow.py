# -*- coding: utf-8 -*-

"""
solph version of oemof.network.Edge

SPDX-FileCopyrightText: Uwe Krien <krien@uni-bremen.de>
SPDX-FileCopyrightText: Simon Hilpert
SPDX-FileCopyrightText: Cord Kaldemeyer
SPDX-FileCopyrightText: Stephan Günther
SPDX-FileCopyrightText: Birgit Schachler
SPDX-FileCopyrightText: Johannes Kochems (jokochems)

SPDX-License-Identifier: MIT

"""

from warnings import warn

from oemof.network import network as on
from oemof.tools import debugging

from oemof.solph import blocks
from oemof.solph.plumbing import sequence


class Flow(on.Edge):
    r"""Defines a flow between two nodes.

    Keyword arguments are used to set the attributes of this flow. Parameters
    which are handled specially are noted below.
    For the case where a parameter can be either a scalar or an iterable, a
    scalar value will be converted to a sequence containing the scalar value at
    every index. This sequence is then stored under the paramter's key.

    Parameters
    ----------
    nominal_value : numeric, :math:`P_{nom}`
        The nominal value of the flow. If this value is set the corresponding
        optimization variable of the flow object will be bounded by this value
        multiplied with min(lower bound)/max(upper bound).
    max : numeric (iterable or scalar), :math:`f_{max}`
        Normed maximum value of the flow. The flow absolute maximum will be
        calculated by multiplying :attr:`nominal_value` with :attr:`max`
    min : numeric (iterable or scalar), :math:`f_{min}`
        Normed minimum value of the flow (see :attr:`max`).
    fix : numeric (iterable or scalar), :math:`f_{actual}`
        Normed fixed value for the flow variable. Will be multiplied with the
        :attr:`nominal_value` to get the absolute value. If :attr:`fixed` is
        set to :obj:`True` the flow variable will be fixed to `fix
        * nominal_value`, i.e. this value is set exogenous.
    positive_gradient : :obj:`dict`, default: `{'ub': None, 'costs': 0}`
        A dictionary containing the following two keys:

         * `'ub'`: numeric (iterable, scalar or None), the normed *upper
           bound* on the positive difference (`flow[t-1] < flow[t]`) of
           two consecutive flow values.
         * `'costs``: numeric (scalar or None), the gradient cost per
           unit.

    negative_gradient : :obj:`dict`, default: `{'ub': None, 'costs': 0}`

        A dictionary containing the following two keys:

          * `'ub'`: numeric (iterable, scalar or None), the normed *upper
            bound* on the negative difference (`flow[t-1] > flow[t]`) of
            two consecutive flow values.
          * `'costs``: numeric (scalar or None), the gradient cost per
            unit.

    summed_max : numeric, :math:`f_{sum,max}`
        Specific maximum value summed over all timesteps. Will be multiplied
        with the nominal_value to get the absolute limit.
    summed_min : numeric, :math:`f_{sum,min}`
        see above
    variable_costs : numeric (iterable or scalar)
        The costs associated with one unit of the flow. If this is set the
        costs will be added to the objective expression of the optimization
        problem.
        Note: In a multiperiod model, nominal costs have to be used which may
        vary on a periodical basis but do not vary within a period.
    fixed : boolean
        Boolean value indicating if a flow is fixed during the optimization
        problem to its ex-ante set value. Used in combination with the
        :attr:`fix`.
    investment : :class:`Investment <oemof.solph.options.Investment>`
        Object indicating if a nominal_value of the flow is determined by
        the optimization problem. Note: This will refer all attributes to an
        investment variable instead of to the nominal_value. The nominal_value
        should not be set (or set to None) if an investment object is used.
    multiperiod : :class:`MultiPeriod <oemof.solph.options.MultiPeriod>`
        Object indicating if a multiperiod flow is needed to be created
        for usage in a MultiPeriodModel
    multiperiodivestment : :class:`MultiPeriodInvestment
        <oemof.solph.options.MultiPeriodInvestment>`
        Object indicating if a nominal_value of the flow is determined by
        the multiperiod optimization problem through investments.
        Note: This will refer all attributes to an multiperiodinvestment
        variable instead of to the nominal_value. The nominal_value
        should not be set (or set to None) if an multiperiodinvestment
        object is used.
    nonconvex : :class:`NonConvex <oemof.solph.options.NonConvex>`
        If a nonconvex flow object is added here, the flow constraints will
        be altered significantly as the mathematical model for the flow
        will be different, i.e. constraint etc. from
        :class:`NonConvexFlow <oemof.solph.blocks.NonConvexFlow>`
        will be used instead of
        :class:`Flow <oemof.solph.blocks.Flow>`.
        Note: at the moment this does not work if the investment attribute is
        set .

    Notes
    -----
    The following sets, variables, constraints and objective parts are created
     * :py:class:`~oemof.solph.blocks.flow.Flow`
     * :py:class:`~oemof.solph.blocks.investment_flow.InvestmentFlow`
        (additionally if Investment object is present)
     * :py:class:`~oemof.solph.blocks.non_convex_flow.NonConvexFlow`
        (If nonconvex  object is present, CAUTION: replaces
        :py:class:`~oemof.solph.blocks.flow.Flow`
        class and a MILP will be build)

    Examples
    --------
    Creating a fixed flow object:

    >>> f = Flow(fix=[10, 4, 4], variable_costs=5)
    >>> f.variable_costs[2]
    5
    >>> f.fix[2]
    4

    Creating a flow object with time-depended lower and upper bounds:

    >>> f1 = Flow(min=[0.2, 0.3], max=0.99, nominal_value=100)
    >>> f1.max[1]
    0.99
    """

    def __init__(self, **kwargs):
        # TODO: Check if we can inherit from pyomo.core.base.var _VarData
        # then we need to create the var object with
        # pyomo.core.base.IndexedVarWithDomain before any Flow is created.
        # E.g. create the variable in the energy system and populate with
        # information afterwards when creating objects.

        super().__init__()

        scalars = ["nominal_value",
                   "summed_max",
                   "summed_min",
                   "investment",
                   "multiperiod",
                   "multiperiodinvestment",
                   "nonconvex",
                   "integer"]
        sequences = ["fix", "variable_costs", "fixed_costs", "min", "max"]
        dictionaries = ["positive_gradient", "negative_gradient"]
        defaults = {
            "variable_costs": 0,
            "positive_gradient": {"ub": None, "costs": 0},
            "negative_gradient": {"ub": None, "costs": 0}
        }
        keys = [k for k in kwargs if k != "label"]

        if 'fixed_costs' in keys:
            msg = ("Be aware that the fixed costs attribute is only\n"
                   "meant to be used for MultiPeriodModels.\n"
                   "It has been decided to remove the `fixed_costs` "
                   "attribute with v0.2 for regular uses!")
            warn(msg, debugging.SuspiciousUsageWarning)

        if "actual_value" in keys:
            raise AttributeError(
                "The `actual_value` attribute has been renamed"
                " to `fix` with v0.4. The attribute `fixed` is"
                " set to True automatically when passing `fix`."
            )

        if "fixed" in keys:
            msg = (
                "The `fixed` attribute is deprecated.\nIf you have defined "
                "the `fix` attribute the flow variable will be fixed.\n"
                "The `fixed` attribute does not change anything."
            )
            warn(msg, debugging.SuspiciousUsageWarning)

        # It is not allowed to define min or max if fix is defined.
        if kwargs.get("fix") is not None and (
            kwargs.get("min") is not None or kwargs.get("max") is not None
        ):
            raise AttributeError(
                "It is not allowed to define min/max if fix is defined."
            )

        # Set default value for min and max
        if kwargs.get("min") is None:
            if "bidirectional" in keys:
                defaults["min"] = -1
            else:
                defaults["min"] = 0
        if kwargs.get("max") is None:
            defaults["max"] = 1

        for attribute in set(scalars + sequences + dictionaries + keys):
            value = kwargs.get(attribute, defaults.get(attribute))
            if attribute in dictionaries:
                setattr(
                    self,
                    attribute,
                    {"ub": sequence(value["ub"]), "costs": value["costs"]},
                )

            else:
                setattr(
                    self,
                    attribute,
                    sequence(value) if attribute in sequences else value,
                )

        # Checking for impossible attribute combinations
        if ((self.investment or self.multiperiodinvestment)
                and self.nominal_value is not None):
            raise ValueError("Using the investment object the nominal_value"
                             " has to be set to None.")
        if ((self.investment or self.multiperiodinvestment)
                and self.nonconvex):
            raise ValueError("Investment flows cannot be combined with "
                             "nonconvex flows!")
        if self.investment and self.multiperiodinvestment:
            raise ValueError("Either use a standard investment flow for "
                             "standard investment models or a "
                             "multiperiodinvestment flow for "
                             "MultiPeriodModels.\n"
                             "Combining both is not feasible!")
        if self.multiperiod is True and self.multiperiodinvestment:
            raise ValueError("In a MultiPeriodModel, a flow can either "
                             "be defined to be a flow for dispatch only,\n"
                             "when setting the attribute `multiperiod` to "
                             "True,\nor it can be defined to be used for "
                             "investments,\nwhen a `multiperiodinvestment` "
                             "object is declared.\nCombining both is not "
                             "feasible!")