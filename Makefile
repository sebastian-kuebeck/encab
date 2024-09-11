.PHONY:	clean_dist dist test validate format apidoc html doc browse publish_test

clean_dist:
	rm -rf dist/*
	rm -f src/encab.egg-info

dist:
	rm -rf dist/*
	python -m build
	rm -f src/encab.egg-info


test:
	python -m unittest discover -v -s tests/unit -p '*_test.py'
	python -m unittest discover -v -s tests/unit/ext -p '*_test.py'

integration_test: clean_dist
	cd tests/integration && make test

load_test: clean_dist
	cd tests/load && make test

reaper_test: clean_dist
	cd tests/reaper && make test

validate:
	mypy --config-file mypy.ini -p encab -p tests
	ruff check src/ tests/

audit:
	pip-audit -r requirements.txt

format:
	black src/encab/*.py src/encab/common/*.py src/encab/ext/*.py tests/unit/*.py tests/unit/ext/*.py tests/integration/*.py tests/load/*.py 

apidoc:
	rm -f docs/encab.rst docs/encab.ext.rst docs/modules.rst
	sphinx-apidoc -o docs src/
	rm -f docs/modules.rst

html:
	cd docs && make clean html && make html

doc: apidoc html

browse_doc:
	firefox docs/_build/html/index.html

publish_test: dist
	twine upload -r testpypi dist/*

publish: dist
	twine upload --repository pypi dist/*

# To run tests with different environments
# 
# Prerequisites:
# - make sure you have pyenv and tox insalled
# - install all python versions using 'pyenv local <versions>' specified in tox.ini
#
# see:
# -	https://github.com/pyenv/pyenv
# - https://tox.wiki
#
tox:
	tox -p

