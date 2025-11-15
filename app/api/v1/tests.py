"""
Knowledge testing endpoints.
"""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.models.mcq import MCQ
from app.models.test import TestAnswer, TestResult
from app.models.user import User
from app.schemas.test import (
    TestResult as TestResultSchema,
    TestResultDetailed,
    TestSubmit,
    TestAnswerResult,
)

router = APIRouter()


@router.post("/submit", response_model=TestResultDetailed, status_code=status.HTTP_201_CREATED)
def submit_test(
    test_data: TestSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Submit test answers and get evaluation.

    Args:
        test_data: Test submission data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Test results with detailed answers

    Raises:
        HTTPException: If MCQs not found or invalid answers
    """
    if not test_data.answers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No answers provided",
        )

    # Fetch all MCQs
    mcq_ids = [answer.mcq_id for answer in test_data.answers]
    mcqs = db.query(MCQ).filter(MCQ.id.in_(mcq_ids)).all()

    if len(mcqs) != len(mcq_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Some MCQs not found",
        )

    # Create MCQ lookup
    mcq_dict = {mcq.id: mcq for mcq in mcqs}

    # Evaluate answers
    correct_count = 0
    answer_results = []

    for answer in test_data.answers:
        mcq = mcq_dict.get(answer.mcq_id)
        if not mcq:
            continue

        is_correct = answer.user_answer.upper() == mcq.correct_answer.upper()
        if is_correct:
            correct_count += 1

        answer_results.append(
            {
                "mcq_id": mcq.id,
                "question": mcq.question,
                "user_answer": answer.user_answer,
                "correct_answer": mcq.correct_answer,
                "is_correct": is_correct,
                "explanation": mcq.explanation,
            }
        )

    # Calculate score
    total_questions = len(test_data.answers)
    score = (correct_count / total_questions) * 100 if total_questions > 0 else 0

    # Create test result
    test_result = TestResult(
        user_id=current_user.id,
        title=test_data.title,
        total_questions=total_questions,
        correct_answers=correct_count,
        score=score,
    )
    db.add(test_result)
    db.flush()

    # Save individual answers
    for answer in test_data.answers:
        mcq = mcq_dict.get(answer.mcq_id)
        if mcq:
            test_answer = TestAnswer(
                test_result_id=test_result.id,
                mcq_id=answer.mcq_id,
                user_answer=answer.user_answer,
                is_correct=answer.user_answer.upper() == mcq.correct_answer.upper(),
            )
            db.add(test_answer)

    db.commit()
    db.refresh(test_result)

    return {
        "id": test_result.id,
        "user_id": test_result.user_id,
        "title": test_result.title,
        "total_questions": test_result.total_questions,
        "correct_answers": test_result.correct_answers,
        "score": test_result.score,
        "completed_at": test_result.completed_at,
        "answers": answer_results,
    }


@router.get("/results", response_model=List[TestResultSchema])
def get_test_results(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get user's test results.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of test results
    """
    results = (
        db.query(TestResult)
        .filter(TestResult.user_id == current_user.id)
        .order_by(TestResult.completed_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return results


@router.get("/results/{result_id}", response_model=TestResultDetailed)
def get_test_result(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get detailed test result by ID.

    Args:
        result_id: Test result ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Detailed test result

    Raises:
        HTTPException: If test result not found or access denied
    """
    test_result = db.query(TestResult).filter(TestResult.id == result_id).first()

    if not test_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test result not found",
        )

    if test_result.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Get detailed answers
    answers = db.query(TestAnswer).filter(TestAnswer.test_result_id == result_id).all()

    answer_results = []
    for answer in answers:
        mcq = db.query(MCQ).filter(MCQ.id == answer.mcq_id).first()
        if mcq:
            answer_results.append(
                {
                    "mcq_id": mcq.id,
                    "question": mcq.question,
                    "user_answer": answer.user_answer,
                    "correct_answer": mcq.correct_answer,
                    "is_correct": answer.is_correct,
                    "explanation": mcq.explanation,
                }
            )

    return {
        "id": test_result.id,
        "user_id": test_result.user_id,
        "title": test_result.title,
        "total_questions": test_result.total_questions,
        "correct_answers": test_result.correct_answers,
        "score": test_result.score,
        "completed_at": test_result.completed_at,
        "answers": answer_results,
    }
