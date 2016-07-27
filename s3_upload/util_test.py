import pytest


@pytest.fixture
def util():
    from util import Util
    return Util()

@pytest.fixture
def json_doc():
    fd = open ("test_fixtures/test13_99_1.json", "rb")
    data = fd.read()
    return data

@pytest.fixture
def json_doc_2():
    fd = open ("test_fixtures/test13_99_2.json", "rb")
    data = fd.read()
    return data


def test_that_we_get_dirname_from_filename(util):
    dir = util.log_directory("13/13000099_HM26I7FZPXXIFW4_Non-Final_Rejection.json")
    assert dir == '13/1300/009/9'


def test_that_we_not_dropping_anything_when_getting_dirname(util):
    dir = util.log_directory("13/13123478_HM26I7FZPXXIFW4_Non-Final_Rejection.json")
    assert dir == '13/1312/347/8'


def test_that_we_get_correct_doc_id(util):
    dir = util.doc_id("13/13123478_HM26I7FZPXXIFW4_Non-Final_Rejection.json")
    assert dir == '13123478, HM26I7FZPXXIFW4'


def test_can_parse_json_file(util, json_doc):

    assert type(json_doc) == bytes
    assert len(json_doc) == 40292

    obj = util.parse_json(json_doc)

    assert obj['type'] == 'oa'
    assert obj['appid'] == '13000099'
    assert "\n" in obj['textdata']


def test_can_reprocess_document(util, json_doc):

    jsontext = util.reprocess_document(json_doc, '13/0000_XXX')

    assert type(jsontext) == str
    assert 's3_url' in jsontext
    assert '"s3_url": "13/0000_XXX' in jsontext


def test_reprocess_removes_NaN_from_dn_intppty_cust_no(util, json_doc_2):

    jsontext = util.reprocess_document(json_doc_2, '13/0000_XXX')

    assert type(jsontext) == str
    assert 'dn_intppty_cust_no' not in jsontext