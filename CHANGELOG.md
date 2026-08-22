# Changelog

## 0.1.0 (2026-08-22)


### ✨ Features

* add the shared scanning engine ([#28](https://github.com/ishuar/aws-resource-inventory/issues/28)) ([e88b581](https://github.com/ishuar/aws-resource-inventory/commit/e88b5817cf32e6fdf7c4df19e98d86a3588159ee))
* scan EFS file systems ([#35](https://github.com/ishuar/aws-resource-inventory/issues/35)) ([0f4ae5e](https://github.com/ishuar/aws-resource-inventory/commit/0f4ae5ee65054ae52a2afabcdfa2548d0ca4213f))
* scan RDS database instances, clusters and snapshots ([#34](https://github.com/ishuar/aws-resource-inventory/issues/34)) ([25419cf](https://github.com/ishuar/aws-resource-inventory/commit/25419cf6ee98802f171394d9c45afc378d15312b))
* tab-completion suggests service names for --service ([#41](https://github.com/ishuar/aws-resource-inventory/issues/41)) ([945ae28](https://github.com/ishuar/aws-resource-inventory/commit/945ae283ef67a51d51be56ed9972e9708eba261d))


### 🐞 Bug Fixes

* bootstrap release manifest at 0.0.0 so the first release is v0.0.1 ([#32](https://github.com/ishuar/aws-resource-inventory/issues/32)) ([6f60dc4](https://github.com/ishuar/aws-resource-inventory/commit/6f60dc4a3d0c1cf8719308eb1267ae11a013f869))
* configuration panel shows the parallelism the scan actually uses ([#38](https://github.com/ishuar/aws-resource-inventory/issues/38)) ([6f6e154](https://github.com/ishuar/aws-resource-inventory/commit/6f6e154088083340caa30e17b458380f324d887f))
* tag scans flatten Auto Scaling resources correctly again ([#36](https://github.com/ishuar/aws-resource-inventory/issues/36)) ([3da5ab4](https://github.com/ishuar/aws-resource-inventory/commit/3da5ab40f2475498be62b196c2c1b59b92f05bb0))
* tag scans report S3 buckets as s3:bucket, not one type per bucket ([#37](https://github.com/ishuar/aws-resource-inventory/issues/37)) ([9178571](https://github.com/ishuar/aws-resource-inventory/commit/91785718211fc52e873efccff74dbf633e5ede98))


### 📦 Other Changes

* add engineering rules (CLAUDE.md) and the aws-inventory waste spec (PRODUCT.md) ([#22](https://github.com/ishuar/aws-resource-inventory/issues/22)) ([1125f5f](https://github.com/ishuar/aws-resource-inventory/commit/1125f5f47cca6732924f011d285a92a01d69c936))
* adopt curated ruff rule set and fix all findings ([#27](https://github.com/ishuar/aws-resource-inventory/issues/27)) ([7925f41](https://github.com/ishuar/aws-resource-inventory/commit/7925f4144b3f963a9e6f440006b208e5a3e66900))
* ec2 and vpc scanners run on the shared scanning engine ([#29](https://github.com/ishuar/aws-resource-inventory/issues/29)) ([439149b](https://github.com/ishuar/aws-resource-inventory/commit/439149b49ca23d2be2076c5201ce8f47cfd97c3b))
* README matches the code — services, structure, commands ([#39](https://github.com/ishuar/aws-resource-inventory/issues/39)) ([9a20ed2](https://github.com/ishuar/aws-resource-inventory/commit/9a20ed269fef5e66dcf1f4cf0b58ae2843283fff))
* rewrite architecture and logging guides to match the current code ([#40](https://github.com/ishuar/aws-resource-inventory/issues/40)) ([257287c](https://github.com/ishuar/aws-resource-inventory/commit/257287c4b36eb65fceeef934c014bdba02053f12))
* s3, ecs, elb and autoscaling scanners run on the shared scanning engine ([#31](https://github.com/ishuar/aws-resource-inventory/issues/31)) ([b3ebfa7](https://github.com/ishuar/aws-resource-inventory/commit/b3ebfa7d4425f51d77625bbf685a4f9f7c395336))
* typed Resource record replaces ad-hoc output dicts ([#33](https://github.com/ishuar/aws-resource-inventory/issues/33)) ([eb72a67](https://github.com/ishuar/aws-resource-inventory/commit/eb72a671331e16236ece6d4346f47ee125ce728b))
