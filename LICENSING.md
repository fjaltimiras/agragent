# Licensing

Copyright (C) 2026 Francisco Altimiras.

agragent is available under two licenses. Choose the one that fits how you use it.

## 1. Open-source license: GNU AGPL v3.0

The code in this repository is licensed under the
[GNU Affero General Public License v3.0](LICENSE) (SPDX: `AGPL-3.0-only`).

This license covers research, teaching, reproducibility and community use. You may use, study, modify
and redistribute agragent, including for commercial purposes, as long as you comply with the AGPL. In
particular:

- If you distribute agragent or a modified version, you must release the complete corresponding source
  code under the AGPL.
- If you run a modified version as a network service (for example, a hosted web platform), you must offer
  the users of that service the complete corresponding source code of your modified version
  (AGPL, section 13).

## 2. Commercial license

A commercial license is available for organisations that want to use agragent without the obligations of
the AGPL. Typical cases:

- offering agragent to their own clients as a hosted service or under their own brand (white label);
- integrating agragent into proprietary software or services without releasing their source code;
- obtaining support, maintenance or warranty terms, which the AGPL does not provide.

The hosted platform at [app.agragent.com](https://app.agragent.com) is offered as a subscription under
commercial terms.

For commercial licensing, white-label agreements or subscriptions, write to **contacto@agragent.com**.

## What each license covers

The dual-licensing offer applies to the code in this repository written by the copyright holder.

It does not change the terms of third-party components, services or data, which keep their own licenses
and terms of use. These include:

- the JavaScript libraries loaded by `app.html` and the model coefficients embedded in
  `assets/indices/sl2p-weights.js` (see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md));
- Google Earth Engine and Copernicus Sentinel-2 data;
- Open-Meteo, Nominatim/OpenStreetMap, OpenAlex, AGRIS and the INIA Digital Library;
- FAOSTAT, whose data are licensed CC BY-NC-SA 3.0 IGO. agragent only queries FAOSTAT at run time and
  does not redistribute its data;
- the LLM inference endpoints configured by the operator.

Anyone who deploys agragent, under either license, is responsible for complying with those terms.

## Trademark

The name "agragent" and the agragent logo are not licensed under either option. Using them requires
permission. A modified version must not be presented as the official agragent service.

## Contributions

Dual licensing only works if every part of the code can be distributed under both licenses. For that
reason, external code contributions can only be accepted under a Contributor License Agreement. See
[CONTRIBUTING.md](CONTRIBUTING.md).
