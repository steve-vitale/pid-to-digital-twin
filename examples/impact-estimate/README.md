# Impact estimate: two worked examples

**Why it matters:** a measured change becomes a cost and emissions figure your manager and sustainability report can
use, with every constant's source shown.

> **Every measured input here is ILLUSTRATIVE.** The pump kW, trap losses, hours and the "site" constants in the
> `*_site.json` specs are made up to show the method. They are not from any real plant. The public typical values used
> with `--use-defaults` are real published figures, cited in each output.

How it works, where each constant comes from, the formulas and the limits: [`docs/IMPACT_ESTIMATE.md`](../../docs/IMPACT_ESTIMATE.md).

| Example | Spec (input) | Constants | First-draft estimate per year (not a verified saving) | Read it |
|---|---|---|---|---|
| Pump moved from throttling to a variable speed drive | [`pump_vfd_site.json`](pump_vfd_site.json) | the user's (illustrative) | 200,000 to 240,000 kWh; $22,800 to $26,400 incl. demand; 84 to 101 t CO2e | [`pump-vfd-site/impact.md`](pump-vfd-site/impact.md) |
| Same pump, measured inputs only | [`pump_vfd_measured.json`](pump_vfd_measured.json) | public typical (`--use-defaults`) | 200,000 to 240,000 kWh; $17,000 to $20,400; 69.9 to 83.9 t CO2e | [`pump-vfd-defaults/impact.md`](pump-vfd-defaults/impact.md) |
| Failed steam traps repaired | [`steam_traps_site.json`](steam_traps_site.json) | the user's (illustrative) | 1,600 to 2,360 MMBtu gas; $8,810 to $13,000; 85.1 to 125 t CO2e | [`steam-traps-site/impact.md`](steam-traps-site/impact.md) |
| Same traps, measured inputs only | [`steam_traps_measured.json`](steam_traps_measured.json) | public typical (`--use-defaults`) | 1,690 to 2,360 MMBtu gas; $8,520 to $11,900; 89.7 to 126 t CO2e | [`steam-traps-defaults/impact.md`](steam-traps-defaults/impact.md) |
| What E1 (pump on a drive) needs | `--needs E1` | | measurements, constants, where to get them | [`needs-E1/needs.md`](needs-E1/needs.md) |
| What E8 (steam traps) needs | `--needs E8` | | measurements, constants, where to get them | [`needs-E8/needs.md`](needs-E8/needs.md) |

Each run writes `impact.md` (readable) and `impact.json` (every input, constant with its origin, formula, substituted
numbers and result). The ranges come from the range inputs (pump kW after 45 to 50 kW; trap losses 150 to 210 lb/h;
boiler efficiency 0.78 to 0.82), carried through by interval arithmetic.

The defaults runs differ from the site runs for plain reasons: no demand charge (there is no public default for it,
so the measured-only pump spec leaves the demand kW out), the US average industrial price instead of the illustrative
tariff, the US average grid factor instead of the illustrative subregion one, DOE's 1,028 Btu/lb (150 psig, 200 F
feedwater) instead of the illustrative 1,000 Btu/lb, and EPA's 80% boiler efficiency assumption instead of the
illustrative 78 to 82% test.

## Regenerate

The test (`scripts/test_estimate_impact.py`) checks these outputs byte for byte and recomputes every total by hand.

```sh
python -S scripts/estimate_impact.py --estimate examples/impact-estimate/pump_vfd_site.json --out examples/impact-estimate/pump-vfd-site
python -S scripts/estimate_impact.py --estimate examples/impact-estimate/pump_vfd_measured.json --use-defaults --out examples/impact-estimate/pump-vfd-defaults
python -S scripts/estimate_impact.py --estimate examples/impact-estimate/steam_traps_site.json --out examples/impact-estimate/steam-traps-site
python -S scripts/estimate_impact.py --estimate examples/impact-estimate/steam_traps_measured.json --use-defaults --out examples/impact-estimate/steam-traps-defaults
python -S scripts/estimate_impact.py --needs E1 --out examples/impact-estimate/needs-E1
python -S scripts/estimate_impact.py --needs E8 --out examples/impact-estimate/needs-E8
```

## Without `--use-defaults`, a missing constant is refused

Running the measured-only trap spec without `--use-defaults` writes nothing and exits 2:

```text
$ python -S scripts/estimate_impact.py --estimate examples/impact-estimate/steam_traps_measured.json
REFUSED: the estimate needs site constants that were not supplied. Supply them in the spec's "site" block, or rerun with --use-defaults to use labelled public typical values where one exists.

- fuel_price_per_mmbtu: fuel use is priced at it
    where: Your gas bill or fuel supply contract: ...
- fuel_kg_co2e_per_mmbtu: fuel CO2e uses it
    where: EPA GHG Emission Factors Hub, Table 1 Stationary Combustion: ...
- boiler_efficiency: steam and heat become fuel through it
    where: Your boiler's efficiency test ...
- changes[1].energy_btu_per_lb: each steam change needs energy_btu_per_lb (your steam-table value)
    where: Steam tables: ...
```

(The real message prints each "where" in full with its URLs.)

## Hand check of all four estimates

Done independently of the tool, and repeated in the test.

**Pump, site constants.** Energy = (75 - 50) x 8,000 = 200,000 kWh to (75 - 45) x 8,000 = 240,000 kWh. Energy cost
= 200,000 x $0.092 = $18,400 to 240,000 x $0.092 = $22,080. Demand = 25 kW x $14.50 x 12 = $4,350. Total $22,750 to
$26,430. CO2e = 200,000 x 0.42 = 84,000 kg to 240,000 x 0.42 = 100,800 kg.

**Pump, defaults.** Cost = 200,000 x $0.0851 = $17,020 to 240,000 x $0.0851 = $20,424. Grid factor = 770.884 lb/MWh x
0.45359237 kg/lb / 1,000 = 0.3496671 kg/kWh; CO2e = 69,933 kg to 83,920 kg.

**Steam traps, site constants.** Heat = 150 x 8,760 x 1,000 / 10^6 = 1,314 MMBtu to 210 x 8,760 x 1,000 / 10^6 =
1,839.6 MMBtu. Fuel = 1,314 / 0.82 = 1,602.44 MMBtu (low: least heat, best boiler) to 1,839.6 / 0.78 = 2,358.46 MMBtu.
Price = $0.55/therm / 0.1 MMBtu/therm = $5.50/MMBtu; cost $8,813.41 to $12,971.54. CO2e = x 53.11 = 85,105 kg to
125,258 kg.

**Steam traps, defaults.** Heat = 150 x 8,760 x 1,028 / 10^6 = 1,350.792 MMBtu to 1,891.109 MMBtu; fuel = / 0.80 =
1,688.49 to 2,363.89 MMBtu. Price = $5.23/Mcf / 1.036 MMBtu/Mcf = $5.048263/MMBtu; cost $8,523.94 to $11,933.5.
CO2e = x 53.1145 kg/MMBtu (53.06 + 1 x 28 / 1,000 + 0.1 x 265 / 1,000) = 89,683 kg to 125,557 kg.
