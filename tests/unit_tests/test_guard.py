import openai
import pytest
from pydantic import BaseModel

from guardrails import Guard, Rail, Validator
from guardrails.datatypes import verify_metadata_requirements
from guardrails.utils.openai_utils import OPENAI_VERSION
from guardrails.validators import PassResult, register_validator


@register_validator("myrequiringvalidator", data_type="string")
class RequiringValidator(Validator):
    required_metadata_keys = ["required_key"]

    def validate(self, value, metadata):
        return PassResult()


@register_validator("myrequiringvalidator2", data_type="string")
class RequiringValidator2(Validator):
    required_metadata_keys = ["required_key2"]

    def validate(self, value, metadata):
        return PassResult()


@pytest.mark.parametrize(
    "spec,metadata,error_message",
    [
        (
            """
<rail version="0.1">
<output>
    <string name="string_name" validators="myrequiringvalidator" />
</output>
</rail>
        """,
            {"required_key": "a"},
            "Missing required metadata keys: required_key",
        ),
        (
            """
<rail version="0.1">
<output>
    <object name="temp_name">
        <string name="string_name" validators="myrequiringvalidator" />
    </object>
    <list name="list_name">
        <string name="string_name" validators="myrequiringvalidator2" />
    </list>
</output>
</rail>
        """,
            {"required_key": "a", "required_key2": "b"},
            "Missing required metadata keys: required_key, required_key2",
        ),
        (
            """
<rail version="0.1">
<output>
    <object name="temp_name">
    <list name="list_name">
    <choice name="choice_name" discriminator="hi">
    <case name="hello">
        <string name="string_name" />
    </case>
    <case name="hiya">
        <string name="string_name" validators="myrequiringvalidator" />
    </case>
    </choice>
    </list>
    </object>
</output>
</rail>
""",
            {"required_key": "a"},
            "Missing required metadata keys: required_key",
        ),
    ],
)
@pytest.mark.asyncio
@pytest.mark.skipif(not OPENAI_VERSION.startswith("0"), reason="Only for OpenAI v0")
async def test_required_metadata(spec, metadata, error_message):
    guard = Guard.from_rail_string(spec)

    missing_keys = verify_metadata_requirements({}, guard.output_schema.root_datatype)
    assert set(missing_keys) == set(metadata)

    not_missing_keys = verify_metadata_requirements(
        metadata, guard.output_schema.root_datatype
    )
    assert not_missing_keys == []

    # test sync guard
    with pytest.raises(ValueError) as excinfo:
        guard.parse("{}")
    assert str(excinfo.value) == error_message

    response = guard.parse("{}", metadata=metadata, num_reasks=0)
    assert response.error is None

    # test async guard
    with pytest.raises(ValueError) as excinfo:
        guard.parse("{}")
        await guard.parse("{}", llm_api=openai.ChatCompletion.acreate, num_reasks=0)
    assert str(excinfo.value) == error_message

    response = await guard.parse(
        "{}", metadata=metadata, llm_api=openai.ChatCompletion.acreate, num_reasks=0
    )
    assert response.error is None


rail = Rail.from_string_validators([], "empty railspec")
empty_rail_string = """<rail version="0.1">
<output
    type="string"
    description="empty railspec"
/>
</rail>"""


class EmptyModel(BaseModel):
    empty_field: str


i_guard_none = Guard(rail)
i_guard_two = Guard(rail, 2)
r_guard_none = Guard.from_rail("tests/unit_tests/test_assets/empty.rail")
r_guard_two = Guard.from_rail("tests/unit_tests/test_assets/empty.rail", 2)
rs_guard_none = Guard.from_rail_string(empty_rail_string)
rs_guard_two = Guard.from_rail_string(empty_rail_string, 2)
py_guard_none = Guard.from_pydantic(output_class=EmptyModel)
py_guard_two = Guard.from_pydantic(output_class=EmptyModel, num_reasks=2)
s_guard_none = Guard.from_string(validators=[], description="empty railspec")
s_guard_two = Guard.from_string(
    validators=[], description="empty railspec", num_reasks=2
)


@pytest.mark.parametrize(
    "guard,expected_num_reasks,config_num_reasks",
    [
        (i_guard_none, 1, None),
        (i_guard_two, 2, None),
        (i_guard_none, 3, 3),
        (r_guard_none, 1, None),
        (r_guard_two, 2, None),
        (r_guard_none, 3, 3),
        (rs_guard_none, 1, None),
        (rs_guard_two, 2, None),
        (rs_guard_none, 3, 3),
        (py_guard_none, 1, None),
        (py_guard_two, 2, None),
        (py_guard_none, 3, 3),
        (s_guard_none, 1, None),
        (s_guard_two, 2, None),
        (s_guard_none, 3, 3),
    ],
)
def test_configure(guard: Guard, expected_num_reasks: int, config_num_reasks: int):
    guard.configure(config_num_reasks)
    assert guard.num_reasks == expected_num_reasks


def guard_init_from_rail():
    guard = Guard.from_rail("tests/unit_tests/test_assets/simple.rail")
    assert (
        guard.instructions.format().source.strip()
        == "You are a helpful bot, who answers only with valid JSON"
    )
    assert guard.prompt.format().source.strip() == "Extract a string from the text"
