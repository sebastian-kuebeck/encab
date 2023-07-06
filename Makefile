.PHONY:	dist doc test validate tox

dist:
	python -m build
	rm -r src/encab.egg-info

test: validate
	python -m unittest discover -p '*_test.py'

validate:
	mypy --config-file mypy.ini -p encab -p tests
	ruff src/ tests/

format:
	black src/encab/*.py src/encab/ext/*.py tests/*.py tests/ext/*.py

apidoc:
	rm -f docs/encab.rst docs/encab.ext.rst docs/modules.rst
	sphinx-apidoc -o docs src/
	rm -f docs/modules.rst

html:
	cd docs && make clean html && make html

doc: apidoc html

browse:
	firefox docs/_build/html/index.html
