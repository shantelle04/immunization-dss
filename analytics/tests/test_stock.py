from immdss_analytics.sim.stock import OPEN_VIAL_DAYS, StockPoint


def point(dpv: int, ovp: bool, doses: int) -> StockPoint:
    sp = StockPoint("X", dpv, ovp)
    sp.receive(doses, "LOT-A", 10_000)
    return sp


def test_discard_policy_wastes_rest_of_opened_vial():
    sp = point(dpv=10, ovp=False, doses=30)
    served, vials, wasted, by_lot = sp.serve(12, date=100)
    assert (served, vials, wasted) == (12, 2, 8)
    assert sp.total() == 10
    assert by_lot == {"LOT-A": 12}


def test_open_vial_policy_keeps_remainder_until_expiry():
    sp = point(dpv=10, ovp=True, doses=20)
    served, vials, wasted, _ = sp.serve(3, date=100)
    assert (served, vials, wasted, sp.open_doses) == (3, 1, 0, 7)
    served, vials, _, _ = sp.serve(5, date=107)
    assert (served, vials, sp.open_doses) == (5, 0, 2)
    assert sp.expire_open_vial(100 + OPEN_VIAL_DAYS - 1) == 0
    assert sp.expire_open_vial(100 + OPEN_VIAL_DAYS) == 2


def test_discard_flag_wastes_open_vial_policy_remainder():
    sp = point(dpv=20, ovp=True, doses=40)
    served, vials, wasted, _ = sp.serve(3, date=100, discard=True)
    assert (served, vials, wasted, sp.open_doses) == (3, 1, 17, 0)


def test_stock_out_serves_only_what_exists():
    sp = point(dpv=1, ovp=True, doses=4)
    served, vials, wasted, _ = sp.serve(9, date=1)
    assert (served, vials, wasted, sp.total()) == (4, 4, 0, 0)


def test_fifo_lots():
    sp = StockPoint("X", 1, True)
    sp.receive(2, "OLD", 50)
    sp.receive(5, "NEW", 90)
    _, _, _, by_lot = sp.serve(3, date=1)
    assert by_lot == {"OLD": 2, "NEW": 1}


def test_losses_remove_whole_vials_oldest_first():
    sp = point(dpv=20, ovp=False, doses=60)
    removed = sp.lose_vials(2)
    assert removed == [("LOT-A", 20), ("LOT-A", 20)]
    assert sp.total() == 20


def test_round_to_vials():
    assert point(dpv=20, ovp=False, doses=0).round_to_vials(41) == 60
    assert point(dpv=20, ovp=False, doses=0).round_to_vials(-5) == 0
