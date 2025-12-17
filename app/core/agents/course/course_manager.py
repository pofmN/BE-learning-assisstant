"""
Course Manager Agent for generating course content from document chunks.
"""
import logging
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, SecretStr

from app.models.document_chunk import DocumentChunk
from app.models.course import Course, CourseSection, Quiz, FlashCard, StudiesNote
from app.core.llm_config import LLMFactory
from app.schemas.flashcard import FlashCardBase, FlashCardList
from app.schemas.course import (
    CourseBase,
    CourseCreate,
    CourseSectionBase,
    QuizBase,
    QuizList,
    StudiesNoteBase,
    StudiesNoteList,
)
from app.core.agents.course.prompts import (
    CLUSTER_SUMMARY_SYSTEM_PROMPT,
    CLUSTER_SUMMARY_USER_PROMPT_TEMPLATE,
    COURSE_METADATA_SYSTEM_PROMPT,
    COURSE_METADATA_USER_PROMPT_TEMPLATE,
    COURSE_OUTLINE_SYSTEM_PROMPT,
    COURSE_OUTLINE_USER_PROMPT_TEMPLATE,
    QUIZ_GENERATION_SYSTEM_PROMPT,
    QUIZ_GENERATION_USER_PROMPT_TEMPLATE,
    STUDIES_NOTE_GENERATION_SYSTEM_PROMPT,
    STUDIES_NOTE_GENERATION_USER_PROMPT_TEMPLATE,
    FLASHCARD_GENERATION_SYSTEM_PROMPT,
    FLASHCARD_GENERATION_USER_PROMPT_TEMPLATE
)

logger = logging.getLogger(__name__)

class ClusterSummary(BaseModel):
    """Schema for cluster summary."""
    summary: str

class LLMCourseSectionList(BaseModel):
    """Schema for LLM generation of course sections."""
    sections: List[CourseSectionBase]

class CourseManagerState(TypedDict):
    """State for course manager agent."""
    document_id: int
    course_config: CourseCreate
    course_id: Optional[int]
    course_metadata: Optional[CourseBase]
    chunks: List[Dict[str, Any]]  # Serialized chunks
    cluster_ids: List[int]
    cluster_summaries: Dict[int, str]
    sections: List[CourseSectionBase]
    quizzes: Dict[int, List[QuizBase]]  # section_id -> quizzes
    flashcards: Dict[int, List[FlashCardBase]]  # section_id -> flashcards
    studies_notes: Dict[int, List[StudiesNoteBase]]  # section_id -> notes
    status: str
    error: Optional[str]

class CourseManagerAgent:
    """
    Agent for managing course generation process.
    """

    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMFactory.create_llm(temperature=0.7, json_mode=True)
        
        self.summary_llm = self.llm.with_structured_output(ClusterSummary)
        self.metadata_llm = self.llm.with_structured_output(CourseBase)
        self.sections_llm = self.llm.with_structured_output(LLMCourseSectionList)
        self.quiz_llm = self.llm.with_structured_output(QuizList)
        self.flashcard_llm = self.llm.with_structured_output(FlashCardList)
        self.note_llm = self.llm.with_structured_output(StudiesNoteList)
        
        self.graph = self._build_graph()
    
    def _build_graph(self) -> CompiledStateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(CourseManagerState)

        # Add nodes
        workflow.add_node("retrieve_chunks", self._retrieve_chunks)
        workflow.add_node("summarize_clusters", self._summarize_clusters)
        workflow.add_node("generate_course_metadata", self._generate_course_metadata)
        workflow.add_node("save_course", self._save_course)
        workflow.add_node("generate_sections", self._generate_sections)
        workflow.add_node("save_sections", self._save_sections)
        workflow.add_node("generate_learning_materials", self._generate_learning_materials)
        workflow.add_node("save_learning_materials", self._save_learning_materials)

        # Define edges
        workflow.set_entry_point("retrieve_chunks")
        workflow.add_edge("retrieve_chunks", "summarize_clusters")
        workflow.add_edge("summarize_clusters", "generate_course_metadata")
        workflow.add_edge("generate_course_metadata", "save_course")
        workflow.add_edge("save_course", "generate_sections")
        workflow.add_edge("generate_sections", "save_sections")
        workflow.add_edge("save_sections", "generate_learning_materials")
        workflow.add_edge("generate_learning_materials", "save_learning_materials")
        workflow.add_edge("save_learning_materials", END)

        return workflow.compile()

    def _retrieve_chunks(self, state: CourseManagerState) -> CourseManagerState:
        """Retrieve document chunks from database."""
        try:
            logger.info(f"Retrieving chunks for document {state['document_id']}")
            chunks = self.db.query(DocumentChunk).filter(
                DocumentChunk.document_id == state['document_id']
            ).order_by(DocumentChunk.cluster_id, DocumentChunk.chunk_index).all()

            if not chunks:
                raise ValueError(f"No chunks found for document {state['document_id']}")

            # Serialize chunks and get unique cluster IDs
            serialized_chunks = []
            cluster_ids = set()
            for chunk in chunks:
                serialized_chunks.append({
                    "id": chunk.id,
                    "chunk_text": chunk.chunk_text,
                    "cluster_id": chunk.cluster_id,
                    "chunk_index": chunk.chunk_index
                })
                if chunk.cluster_id is not None:
                    cluster_ids.add(chunk.cluster_id)

            return {
                **state,
                "chunks": serialized_chunks,
                "cluster_ids": sorted(list(cluster_ids)),
                "status": "chunks_retrieved"
            }
        except Exception as e:
            logger.error(f"Error retrieving chunks: {e}")
            return {**state, "error": str(e), "status": "error"}

    def _summarize_clusters(self, state: CourseManagerState) -> CourseManagerState:
        """Summarize clusters - use temporary executor."""
        try:
            logger.info("Summarizing clusters in parallel...")
            
            def summarize_single_cluster(cluster_id):
                cluster_chunks = [
                    c["chunk_text"] for c in state["chunks"] 
                    if c["cluster_id"] == cluster_id
                ]
                combined_text = "\n\n".join(cluster_chunks)
                messages = [
                    SystemMessage(content=CLUSTER_SUMMARY_SYSTEM_PROMPT),
                    HumanMessage(content=CLUSTER_SUMMARY_USER_PROMPT_TEMPLATE.format(content=combined_text))
                ]
                response = self.summary_llm.invoke(messages)
                return cluster_id, response.summary # type: ignore
            
            # Use context manager for executor
            with ThreadPoolExecutor(max_workers=min(5, len(state["cluster_ids"]))) as executor:
                futures = [
                    executor.submit(summarize_single_cluster, cid) 
                    for cid in state["cluster_ids"]
                ]
                cluster_summaries = {cid: summary for cid, summary in [f.result() for f in futures]}
            
            return {
                **state,
                "cluster_summaries": cluster_summaries,
                "status": "clusters_summarized"
            }
        except Exception as e:
            logger.error(f"Error summarizing clusters: {e}", exc_info=True)
            return {**state, "error": str(e), "status": "error"}

    def _generate_course_metadata(self, state: CourseManagerState) -> CourseManagerState:
        """Generate comprehensive course metadata using LLM."""
        try:
            logger.info("Generating course metadata...")
            
            # Combine all summaries for context
            combined_summaries = ""
            for cluster_id, summary in state["cluster_summaries"].items():
                combined_summaries += f"{summary}\n\n"
            
            config = state["course_config"]
            
            messages = [
                SystemMessage(content=COURSE_METADATA_SYSTEM_PROMPT),
                HumanMessage(content=COURSE_METADATA_USER_PROMPT_TEMPLATE.format(
                    level=config.level or "Mixed",
                    language=config.language or "English",
                    requirements=config.requirements or "None",
                    summaries=combined_summaries
                ))
            ]
            
            metadata = self.metadata_llm.invoke(messages)
            
            return {
                **state,
                "course_metadata": metadata,  # type: ignore
                "status": "course_metadata_generated"
            }
        except Exception as e:
            logger.error(f"Error generating course metadata: {e}", exc_info=True)
            return {**state, "error": str(e), "status": "error"}

    def _save_course(self, state: CourseManagerState) -> CourseManagerState:
        """Update existing course with generated metadata."""
        try:
            logger.info("Updating course with generated metadata...")
            
            config = state["course_config"]
            metadata = state.get("course_metadata")
            
            # Update existing course instead of creating new one
            course = self.db.query(Course).filter(Course.id == state["course_id"]).first()
            
            if not course:
                raise ValueError(f"Course with id {state['course_id']} not found")
            
            # Update fields with generated metadata
            course.title = metadata.title if metadata else "Generated Course"  # type: ignore
            course.description = metadata.description if metadata else "No description provided."  # type: ignore
            course.language = metadata.language if metadata else config.language  # type: ignore
            course.level = metadata.level if metadata else config.level  # type: ignore
            course.requirements = metadata.requirements if metadata else config.requirements  # type: ignore
            course.question_type = ",".join(config.question_type) if config.question_type else "multiple_choice" # type: ignore
            # Status remains "processing" until completion
            
            self.db.flush()
            
            return {
                **state,
                "status": "course_saved"
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating course: {e}", exc_info=True)
            return {**state, "error": str(e), "status": "error"}

    def _generate_sections(self, state: CourseManagerState) -> CourseManagerState:
        """Generate course sections from cluster summaries."""
        try:
            logger.info("Generating course sections...")
            
            # Combine all summaries
            combined_summaries = ""
            for cluster_id, summary in state["cluster_summaries"].items():
                combined_summaries += f"Cluster {cluster_id}:\n{summary}\n\n"
            
            config = state["course_config"]
            
            messages = [
                SystemMessage(content=COURSE_OUTLINE_SYSTEM_PROMPT),
                HumanMessage(content=COURSE_OUTLINE_USER_PROMPT_TEMPLATE.format(
                    language=config.language or "English",
                    level=config.level or "Beginner",
                    requirements=config.requirements or "None",
                    summaries=combined_summaries
                ))
            ]
            
            sections_list = self.sections_llm.invoke(messages)
            
            return {
                **state,
                "sections": sections_list.sections,  # type: ignore
                "status": "sections_generated"
            }
        except Exception as e:
            logger.error(f"Error generating sections: {e}", exc_info=True)
            return {**state, "error": str(e), "status": "error"}

    def _save_sections(self, state: CourseManagerState) -> CourseManagerState:
        """Save generated sections to database."""
        try:
            logger.info("Saving sections to database...")
            
            for section_data in state["sections"]:
                section = CourseSection(
                    course_id=state["course_id"],
                    title=section_data.title,
                    content=section_data.content,
                    section_order=section_data.section_order,
                    cluster_id=section_data.cluster_id,
                    key_points=section_data.key_points
                )
                self.db.add(section)
            
            self.db.commit()
            
            return {
                **state,
                "status": "sections_saved"
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving sections: {e}", exc_info=True)
            return {**state, "error": str(e), "status": "error"}

    def _generate_learning_materials(self, state: CourseManagerState) -> CourseManagerState:
        """Generate quizzes, flashcards, and study notes in parallel."""
        try:
            logger.info("Generating learning materials (quizzes, flashcards, notes) in parallel...")
            
            saved_sections = self.db.query(CourseSection).filter(
                CourseSection.course_id == state["course_id"]
            ).all()
            
            def generate_materials_for_section(section):
                """Generate all materials for a single section."""
                if section.cluster_id is None:
                    return section.id, [], [], []
                
                cluster_chunks = [
                    c["chunk_text"] for c in state["chunks"] 
                    if c["cluster_id"] == section.cluster_id
                ]
                combined_text = "\n\n".join(cluster_chunks)
                context = combined_text[:20000]
                
                # Common parameters
                common_params = {
                    "title": section.title,
                    "content": section.content,
                    "language": state["course_config"].language or "English",
                    "level": state["course_config"].level or "Mixed",
                    "context": context
                }
                
                # Generate quiz
                quiz_messages = [
                    SystemMessage(content=QUIZ_GENERATION_SYSTEM_PROMPT),
                    HumanMessage(content=QUIZ_GENERATION_USER_PROMPT_TEMPLATE.format(
                        **common_params,
                        question_types=",".join(state["course_config"].question_type or ["multiple_choice"]),
                        requirements=state["course_config"].requirements or "None"
                    ))
                ]
                
                # Generate flashcards
                flashcard_messages = [
                    SystemMessage(content=FLASHCARD_GENERATION_SYSTEM_PROMPT),
                    HumanMessage(content=FLASHCARD_GENERATION_USER_PROMPT_TEMPLATE.format(**common_params))
                ]
                
                # Generate study notes
                note_messages = [
                    SystemMessage(content=STUDIES_NOTE_GENERATION_SYSTEM_PROMPT),
                    HumanMessage(content=STUDIES_NOTE_GENERATION_USER_PROMPT_TEMPLATE.format(**common_params))
                ]
                
                # Parallel generation within section
                with ThreadPoolExecutor(max_workers=3) as inner_executor:
                    quiz_future = inner_executor.submit(self.quiz_llm.invoke, quiz_messages)
                    flashcard_future = inner_executor.submit(self.flashcard_llm.invoke, flashcard_messages)
                    note_future = inner_executor.submit(self.note_llm.invoke, note_messages)
                    
                    quiz_list = quiz_future.result()
                    flashcard_list = flashcard_future.result()
                    note_list = note_future.result()
                
                logger.info(f"Generated materials for section {section.id}: {section.title}")
                return (
                    section.id,
                    quiz_list.questions,  # type: ignore
                    flashcard_list.flashcards,  # type: ignore
                    note_list.notes  # type: ignore
                )
            
            # Parallel execution across sections
            with ThreadPoolExecutor(max_workers=min(5, len(saved_sections))) as executor:
                futures = [
                    executor.submit(generate_materials_for_section, section) 
                    for section in saved_sections
                ]
                
                quizzes_map = {}
                flashcards_map = {}
                notes_map = {}
                
                for future in as_completed(futures):
                    try:
                        section_id, quizzes, flashcards, notes = future.result()
                        quizzes_map[section_id] = quizzes
                        flashcards_map[section_id] = flashcards
                        notes_map[section_id] = notes
                    except Exception as e:
                        logger.error(f"Error generating materials for a section: {e}")
                        continue
            
            logger.info(f"Completed materials generation for {len(quizzes_map)} sections")
            
            return {
                **state,
                "quizzes": quizzes_map,
                "flashcards": flashcards_map,
                "studies_notes": notes_map,
                "status": "learning_materials_generated"
            }
        except Exception as e:
            logger.error(f"Error generating learning materials: {e}", exc_info=True)
            return {**state, "error": str(e), "status": "error"}

    def _save_learning_materials(self, state: CourseManagerState) -> CourseManagerState:
        """Save generated quizzes, flashcards, and study notes to database."""
        try:
            logger.info("Saving learning materials to database...")
            
            # Save quizzes
            for section_id, questions in state["quizzes"].items():
                for q in questions:
                    q_data = q.to_db_format()
                    quiz = Quiz(
                        course_id=state["course_id"],
                        section_id=section_id,
                        question=q.question,
                        question_type=q.question_type,
                        question_data=q_data,
                        explanation=q.explanation,
                        difficulty=q.difficulty
                    )
                    self.db.add(quiz)
            
            # Save flashcards
            for section_id, flashcards in state["flashcards"].items():
                for fc in flashcards:
                    flashcard = FlashCard(
                        course_id=state["course_id"],
                        section_id=section_id,
                        question=fc.question,
                        answer=fc.answer
                    )
                    self.db.add(flashcard)
            
            # Save study notes
            for section_id, notes in state["studies_notes"].items():
                for note in notes:
                    study_note = StudiesNote(
                        course_id=state["course_id"],
                        section_id=section_id,
                        title=note.title,
                        content=note.content
                    )
                    self.db.add(study_note)
            
            # Update course status to completed
            course = self.db.query(Course).filter(Course.id == state["course_id"]).first()
            if course:
                setattr(course, "status", "completed")
            
            self.db.commit()
            
            return {
                **state,
                "status": "completed"
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving learning materials: {e}", exc_info=True)
            return {**state, "error": str(e), "status": "error"}

    def run(self, course_id: int, course_config: CourseCreate) -> Dict[str, Any]:
        """Run the course generation workflow."""
        initial_state = CourseManagerState(
            document_id=course_config.document_id,
            course_config=course_config,
            course_id=course_id,
            course_metadata=None,
            chunks=[],
            cluster_ids=[],
            cluster_summaries={},
            sections=[],
            quizzes={},
            flashcards={},
            studies_notes={},
            status="started",
            error=None
        )
        
        result = self.graph.invoke(initial_state)
        return result
