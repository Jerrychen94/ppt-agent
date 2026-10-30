TOOLS ?= ../scripts

.PHONY: help demo run evals smoke test check baseline clean

help:
	@echo "make demo     跑一条完整示例（离线 mock，输出到 tmp/demo）"
	@echo "make evals    跑全部评测用例"
	@echo "make smoke    只跑 smoke 用例"
	@echo "make test     单元测试"
	@echo "make check    结构自检（需 ../scripts/check-structure.py）"
	@echo "make baseline 评测全绿后更新基线"
	@echo "make clean    删除 tmp/"

demo:
	@python3 src/ppt.py --root tmp/demo --slug demo init \
		--topic "让 AI 成为团队的第二双手" --slides 9 --theme swiss \
		--audience "研发管理者" --goal "说服团队在下季度试点 AI 编程助手" \
		--presenter "Jerry" --date "2026-10" \
		--points "人均每周节省 4.2 小时;代码评审一次通过率提升 18%;新成员上手周期从 6 周降到 3 周;先从两个小组试点;建立提示词与代码规范;每两周复盘一次数据" \
		--force >/dev/null
	@python3 src/ppt.py --root tmp/demo --slug demo pipeline

run: demo

evals:
	python3 $(TOOLS)/run-evals.py .

smoke:
	python3 $(TOOLS)/run-evals.py . --tag smoke

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

check:
	python3 $(TOOLS)/check-structure.py .

baseline:
	python3 $(TOOLS)/run-evals.py . --update-baseline

clean:
	rm -rf tmp
