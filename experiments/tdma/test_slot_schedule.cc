#include "slot_schedule.hh"
#include <cassert>
#include <iostream>
#include <stdexcept>

int main()
{
    using tdma::SlotSchedule;
    SlotSchedule s(4000);
    assert(s.owner(0) == 0 && s.owner(3999) == 0);
    assert(s.owner(4000) == 1 && s.owner(7999) == 1);
    assert(s.owner(8000) == 0);
    assert(s.eligible(0, 0) && !s.eligible(1, 0));
    assert(!s.eligible(0, 1) && !s.eligible(4000, 0));
    s.grant(0, 0);
    assert(!s.eligible(0, 0));
    assert(s.next(0, 0) == 8000 && s.next(1, 0) == 8000);
    assert(s.next(0, 1) == 4000 && s.next(4000, 1) == 12000);
    assert(s.fits(3000) && !s.fits(4000) && !s.fits(4001));
    bool invalid = false;
    try { SlotSchedule bad(0); } catch (const std::invalid_argument&) { invalid = true; }
    assert(invalid);
    invalid = false;
    try { s.grant(4000, 0); } catch (const std::logic_error&) { invalid = true; }
    assert(invalid);
    std::cout << "PASS slot ownership, boundaries, strict retry, single grant, transport bound\n";
}
