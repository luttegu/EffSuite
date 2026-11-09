# Compare with EFFTRAN — laboratory evaluation

Use exactly the same detector/source dimensions, materials, composition,
calibration, decay data and physical case. Retain original input/output files
and record both program versions. Compare transfer factors and efficiencies
separately from summing activity multipliers. All three are dimensionless.

Original EFFTRAN/MEFFTRAN coincidence factors are printed to three decimals;
this suite prints more digits. Record that quantization when defining the
comparison criterion. Small sum-peak factors can print as zero in the original.
Do not confuse a difference in printed precision with a validated physics change.

The well backend deliberately changes the reproduced unstable spatial summing
calculation. Agreement with a known bad negative/near-singular legacy value is
not the acceptance target. Test independent measured reference cases across
sample heights, density/materials, detector well dimensions and nuclides,
including sample boundaries near and above the crystal rim. Document intended
use, acceptance criteria, uncertainty treatment, deviations and laboratory
release approval before routine use. Compatibility with EFFTRAN by itself does
not establish independent physical validity.

## Optional strict comparison tool

The ordinary result CSVs are ready for inspection. For a controlled paired
comparison, copy `comparison/results_template.csv` twice and fill reference
and candidate records. The header-only template intentionally cannot pass.
`source_file` names a retained evidence file relative to each CSV;
`source_sha256` must be its actual SHA-256. On Windows:

```powershell
Get-FileHash .\original_output.txt -Algorithm SHA256
```

Use the same case_id, geometry, detector_id, sample_id, input_set_id, nuclide
and line_id for each matched pair. Stable line IDs are required, including for
same-energy transitions. For transfer/efficiency, nuclide can be empty.

| quantity | unit | convention |
|---|---|---|
| full_energy_efficiency | 1 | absolute_probability |
| transfer_factor | 1 | multiply_reference_efficiency |
| summing_activity_multiplier | 1 | multiply_activity |

Fill `criteria_template.json` with the laboratory's predeclared tolerances for
the geometry/quantity families used. Remove unused entries. Null tolerances
are deliberately rejected; no scientific acceptance limit is supplied by this
package. The numeric criterion is `abs(candidate-reference) <= atol +
rtol*abs(reference)`. Energies also require an explicit tolerance. Record program
versions/builds and the plan ID. Set approval metadata only after actual approval;
the file records that metadata but does not authenticate it.

```bat
Compare_Lab.bat --reference reference.csv --candidate candidate.csv --criteria criteria.json --output comparison.json
```

An optional standardized-difference check needs absolute standard uncertainties
(k=1) for both results and a covariance JSON entry per pair. Never assume zero
cross-covariance merely because two programs were used. Shared inputs/models
can correlate their results. With an explicit justified covariance, the tool
uses `u_difference² = u_candidate² + u_reference² - 2*covariance`.
The optional JSON list uses case_id, quantity, nuclide, line_id, covariance and
a nonempty basis. Supply it with `--covariance covariance.json`.

Missing/duplicate/extra lines, changed evidence, inconsistent units/directions,
undeclared criteria and impossible covariance are rejected. Exit 0 denotes a
passing comparison under declared approved criteria; 1 denotes an unapproved
or failing comparison; 2 denotes invalid input. Every report explicitly says
`routine_use_authorized: false`. This tool cannot certify the software.
