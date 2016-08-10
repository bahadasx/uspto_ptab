import pytest


@pytest.fixture
def uploader():
    from s3_uploader import S3Uploader
    return S3Uploader('uspto-bdr')


def xtest_that_we_can_post_file_to_s3(uploader):
    uploader.post_file("test_fixtures/test_file.txt", '9900011_Test99', 'T99')



def xtest_that_we_can_retrieve_list_of_files_14(uploader):
    files = uploader.get_file_list("14")

    count = sum(1 for x in files)

    assert count == 170867


def xtest_that_we_can_retrieve_list_of_files_13(uploader):

    files = uploader.get_file_list("13/")

    count = sum(1 for x in files)
    assert count == 382682

def xtest_that_we_can_retrieve_list_of_files_14s(uploader):

    files = uploader.get_file_list("14s/")

    count = sum(1 for x in files)
    assert count == 240542

def test_that_we_can_retrieve_list_of_files_14m(uploader):

    files = uploader.get_file_list("14m/")

    count = sum(1 for x in files)
    assert count == 5456

def test_that_we_can_retrieve_list_of_files_13m(uploader):

    files = uploader.get_file_list("13m/")

    count = sum(1 for x in files)
    assert count == 181685

def xtest_that_we_can_retrieve_list_of_files_13s(uploader):

    files = uploader.get_file_list("13s/")

    count = sum(1 for x in files)
    assert count == 878744

def xtest_that_we_can_get_subset_of_data(uploader):

    files = uploader.get_file_list("13/130000")
    files = list(files)

    assert 152 == len(files)
    assert files[0].key == '13/13000002_HC0HIXUBPXXIFW4_Non-Final_Rejection.json'

    file = files[0].get()

    assert file['Body'].read().startswith(b'{"type": "oa", "appid": "13000002", '
                                          b'"ifwnumber": "HC0HIXUBPXXIFW4", "documentcode": "CTNF",')
