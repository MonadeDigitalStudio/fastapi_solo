class FastapiSoloConfig:
    pagination_size = 20
    queryable_use_like = False
    delete_status_code = 204
    swagger_filters = False  # don't use in production, it can impact performance
    include_first_level_relationships = False  # can impact performance
