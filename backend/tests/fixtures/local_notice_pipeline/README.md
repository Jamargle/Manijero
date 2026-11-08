# local_notice_pipeline fixtures

Every notice under `notices/` is **invented** for tests: no real cooperative, person, or
notice. `fake_model_outputs.json` holds canned model replies keyed by notice file name; it is
not real model output. Personal-looking and injected samples are built inside the tests, never
committed as files. Real notices come later from the owner and stay outside the repository.
