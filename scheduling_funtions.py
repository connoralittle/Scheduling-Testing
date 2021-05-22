import itertools
import re
import typing


def window(seq, n=2):
    "Returns a sliding window (of width n) over data from the iterable"
    "   s -> (s0,s1,...s[n-1]), (s1,s2,...,sn), ...                   "
    it = iter(seq)
    result = tuple(itertools.islice(it, n))
    if len(result) == n:
        yield result
    for elem in it:
        result = result[1:] + (elem,)
        yield result


def detect_pattern(list, pattern):
    return False if re.search(pattern, ''.join([str(i) for i in list])) is None else True


def detect_pattern_soft(list, pattern):
    return len(re.findall(pattern, ''.join([str(i) for i in list])))

def not_list(my_list: typing.List):
    return list(map(lambda x: x.Not(), my_list))

# https://github.com/google/or-tools/blob/master/examples/python/shift_scheduling_sat.py


def bounded_span(shifts, start, length, left_bound):
    sequence = []
    # Left border (start of works, or works[start - 1])
    if start > 0 and left_bound:
        sequence.append(shifts[start - 1].Not())

    for i in range(length):
        sequence.append(shifts[start + i])

    # Right border (end of works or works[start + length])
    if start + length < len(shifts):
        sequence.append(shifts[start + length].Not())
    return sequence


def predicates(start, prior, prior_shifts):
    return [prior_shifts[i + start].Not() if prior[i] == 0 else prior_shifts[i + start]
               for i in range(len(prior))]


def forbid_min(model, shifts, hard_min, prior = [], prior_shifts=[], continue_prior=False):
    # Forbid sequences that are too short.
    prior_shifts = shifts if prior_shifts == [] else prior_shifts

    for length in range(1, hard_min):
        window_size = len(shifts) - length - len(prior)  + 1
        for start in range(window_size):
            pred = predicates(start, prior,
                              prior_shifts)
            span = bounded_span(shifts, start + len(prior),
                                length, prior == [])
            print(pred)
            print(span)
            print((shifts[start + len(prior) : start + len(prior) + length]))
            print()

            if continue_prior and start < window_size - len(prior):
                and_window = start + len(prior) + length - 1
                model.AddBoolAnd([prior_shifts[and_window], shifts[and_window]]).OnlyEnforceIf(pred + [shifts[and_window]])
                model.AddBoolOr(span).OnlyEnforceIf(pred)
            elif prior != []:
                model.AddBoolAnd(not_list(shifts[start +  len(prior) : start + len(prior) + hard_min])).OnlyEnforceIf(pred)
            else:
                model.AddBoolOr(span)

def forbid_max(model, shifts, hard_max, prior=[], prior_shifts=[], continue_prior=False):
    # Just forbid any sequence of true variables with length hard_max + 1

    window_size = len(shifts) - hard_max - len(prior) + 1
    for start in range(window_size):
        pred = predicates(start, prior,
                          prior_shifts)
        span = bounded_span(shifts, start + len(prior),
                            hard_max, False)
        if continue_prior and start < window_size - len(prior):
            and_window = start + len(prior) + hard_max - 1
            model.AddBoolAnd([prior_shifts[and_window], shifts[and_window]]).OnlyEnforceIf(pred + [shifts[and_window]])
            model.AddBoolOr(span).OnlyEnforceIf(pred)
        elif prior != []:
            model.AddBoolAnd(not_list(shifts[start +  len(prior) : start + len(prior) + hard_max])).OnlyEnforceIf(pred)
        else:
            model.AddBoolOr(span)


def penalize_min(model, shifts, hard_min, soft_min, min_cost, prefix, prior=[], prior_shifts=[], continue_prior=False):
    cost_literals = []
    cost_coefficients = []

  # Penalize sequences that are below the soft limit.
    for length in range(hard_min, soft_min):
        window_size = len(prior_shifts) - length - len(prior) + 1
        for start in range(window_size):
            pred = predicates(start, prior,
                              prior_shifts)
            span = bounded_span(shifts, start + len(prior),
                                length, prior == [])
            name = ': under_span(start=%i, length=%i)' % (start, length)
            lit = model.NewBoolVar(prefix + name)
            span.append(lit)
            if continue_prior and start < window_size - 1:
                and_window = start + len(prior) + length - 1
                model.AddBoolAnd([prior_shifts[and_window], shifts[and_window]]).OnlyEnforceIf(pred + [shifts[and_window]])
                model.AddBoolOr(span).OnlyEnforceIf(pred)
            elif prior != []:
                not_sequence = model.NewBoolVar('not_sequence')
                model.Add(sum(shifts[start +  len(prior) : start + len(prior) + length]) == len(shifts[start +  len(prior) : start + len(prior) + length])) \
                    .OnlyEnforceIf(pred + [not_sequence])
                model.AddBoolOr([not_sequence, lit]).OnlyEnforceIf(pred)
            else:
                model.AddBoolOr(span)
            cost_literals.append(lit)
            # We filter exactly the sequence with a short length.
            # The penalty is proportional to the delta with soft_min.
            cost_coefficients.append(min_cost * (soft_min - length))

    return cost_literals, cost_coefficients


def penalize_max(model, shifts, hard_max, soft_max, max_cost, prefix, prior=[], prior_shifts=[], continue_prior=False):
    cost_literals = []
    cost_coefficients = []

    for length in range(soft_max + 1, hard_max + 1):
        window_size = len(shifts) - length - len(prior)
        for start in range(window_size):
            pred = predicates(start, prior,
                              prior_shifts)
            span = bounded_span(shifts, start + len(prior),
                                length, prior == [])
            name = ': over_span(start=%i, length=%i)' % (start, length)
            lit = model.NewBoolVar(prefix + name)
            span.append(lit)
            if continue_prior and start < window_size - 1:
                and_window = start + len(prior) + length - 1
                model.AddBoolAnd([prior_shifts[and_window], shifts[and_window]]).OnlyEnforceIf(pred + [shifts[and_window]])
                model.AddBoolOr(span).OnlyEnforceIf(pred)
            elif prior != []:
                not_sequence = model.NewBoolVar('not_sequence')
                model.Add(sum(shifts[start +  len(prior) : start + len(prior) + length]) == len(shifts[start +  len(prior) : start + len(prior) + length])) \
                    .OnlyEnforceIf(pred + [not_sequence])
                model.AddBoolOr([not_sequence, lit]).OnlyEnforceIf(pred)
            else:
                model.AddBoolOr(span)
            cost_literals.append(lit)
            # Cost paid is max_cost * excess length.
            cost_coefficients.append(max_cost * (length - soft_max))

    return cost_literals, cost_coefficients


def add_soft_sequence_min_constraint(model, shifts, hard_min, soft_min, min_cost, prefix,
                                     prior=[], prior_shifts=[], continue_prior=False):
    forbid_min(model, shifts, hard_min, prior, 
               prior_shifts, continue_prior)
    return penalize_min(model, shifts, hard_min, soft_min, min_cost, prefix,
                 prior, prior_shifts, continue_prior)


def add_soft_sequence_max_constraint(model, shifts, hard_max, soft_max, max_cost, prefix,
                                     prior=[], prior_shifts=[], continue_prior=False):
    forbid_max(model, shifts, hard_max, prior,
               prior_shifts, continue_prior)
    return penalize_max(model, shifts, hard_max, soft_max, max_cost, prefix, prior, prior_shifts, continue_prior)


def add_soft_sequence_constraint(model, shifts, hard_min, soft_min, min_cost,
                                 soft_max, hard_max, max_cost, prefix,
                                 prior=[], prior_shifts=[], continue_prior=False):
    forbid_min(model, shifts, hard_min, prior,
               prior_shifts,continue_prior)
    forbid_max(model, shifts, hard_max, prior,
               prior_shifts, continue_prior)
    var1, coeff1 = penalize_min(
        model, shifts, hard_min, soft_min, min_cost, prefix, prior, prior_shifts, continue_prior)
    var2, coeff2 = penalize_max(
        model, shifts, hard_max, soft_max, max_cost, prefix, prior, prior_shifts, continue_prior)
    return (var1 + var2), (coeff1 + coeff2)

def add_soft_sum_constraint(model, shifts, hard_min, soft_min, min_cost,
                            soft_max, hard_max, max_cost, prefix):

    cost_variables = []
    cost_coefficients = []
    sum_var = model.NewIntVar(hard_min, hard_max, '')
    # This adds the hard constraints on the sum.
    model.Add(sum_var == sum(shifts))

    # Penalize sums below the soft_min target.
    if soft_min > hard_min and min_cost > 0:
        delta = model.NewIntVar(-len(shifts), len(shifts), '')
        model.Add(delta == soft_min - sum_var)
        # TODO(user): Compare efficiency with only excess >= soft_min - sum_var.
        excess = model.NewIntVar(0, 7, prefix + ': under_sum')
        model.AddMaxEquality(excess, [delta, 0])
        cost_variables.append(excess)
        cost_coefficients.append(min_cost)

    # Penalize sums above the soft_max target.
    if soft_max < hard_max and max_cost > 0:
        delta = model.NewIntVar(-7, 7, '')
        model.Add(delta == sum_var - soft_max)
        excess = model.NewIntVar(0, 7, prefix + ': over_sum')
        model.AddMaxEquality(excess, [delta, 0])
        cost_variables.append(excess)
        cost_coefficients.append(max_cost)

    return cost_variables, cost_coefficients
