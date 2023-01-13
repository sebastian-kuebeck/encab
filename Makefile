.PHONY:	dist doc test validate tox

dist:
	python -m build
	rm -r src/encab.egg-info

doc:
	sphinx-build -b html docs/source/ build/html

test: validate
	python -m unittest tests/all_tests.py

validate:
	mypy --config-file mypy.ini -p encab -p tests

format:
	black src/encab/*.py src/encab/ext/*.py tests/*.py tests/ext/*.py

tox: 
	tox
