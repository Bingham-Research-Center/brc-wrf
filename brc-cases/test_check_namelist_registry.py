from check_namelist_registry import check,declarations

DECL='''NAMELIST /physics/ tracer_pblmix
NAMELIST /dynamics/ tracer_adv_opt
NAMELIST /namelist_quilt/ nio_tasks_per_group, nio_groups, poll_servers
'''


def test_compiled_groups_and_manual_quilting_group():
    nml='&physics\n tracer_pblmix = 1, 1,\n/\n&dynamics\n tracer_adv_opt = 1, 1,\n/\n&namelist_quilt\n nio_tasks_per_group = 0,\n nio_groups=1,\n/\n'
    assert check(nml,declarations(DECL))=={'keys_checked':4,'errors':[],'accepted_groups':True}


def test_mixing_in_dynamics_is_rejected():
    result=check('&dynamics\n tracer_pblmix=1,1,\n/\n',declarations(DECL))
    assert not result['accepted_groups']
    assert result['errors'][0]['compiled_group']=='physics'


def test_unknown_and_duplicate_keys_are_rejected():
    result=check('&physics\n tracer_pblmix=1,1,\n tracer_pblmix=1,1,\n not_a_key=1,\n/\n',declarations(DECL))
    assert not result['accepted_groups'] and len(result['errors'])==2
